#!/usr/bin/env python3
"""Single (or repeated) Gemini generate_content using the same google.genai path as the agent.

Examples:
  ./.venv/bin/python scripts/gemini_one_shot_latency.py
  ./.venv/bin/python scripts/gemini_one_shot_latency.py --probe-only
  ./.venv/bin/python scripts/gemini_one_shot_latency.py --idle-seconds 125
  ./.venv/bin/python scripts/gemini_one_shot_latency.py --repeat 2

After ~2 min idle, compare latency to a back-to-back run: if only the API call is ~300s but
HTTPS probe to the same host is sub-second, slow home bandwidth is an unlikely root cause
(the stall is waiting on the generation response, not on reaching Google).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from app.config import get_settings  # noqa: E402

GEMINI_API_HOST = "https://generativelanguage.googleapis.com/"


def probe_network() -> tuple[float, int]:
    """Time a simple HTTPS GET to the Gemini API host (status may be 404; we care about RTT)."""
    t0 = time.perf_counter()
    with httpx.Client(timeout=15.0) as client:
        r = client.get(GEMINI_API_HOST)
    return time.perf_counter() - t0, r.status_code


def run_once(
    client: genai.Client,
    model: str,
    prompt: str,
    config: types.GenerateContentConfig,
) -> tuple[float, str]:
    t0 = time.perf_counter()
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    elapsed = time.perf_counter() - t0
    text = getattr(response, "text", None) or ""
    return elapsed, text


def main() -> None:
    p = argparse.ArgumentParser(description="Gemini one-shot latency / network probe")
    p.add_argument(
        "--probe-only",
        action="store_true",
        help="Only measure HTTPS latency to generativelanguage.googleapis.com",
    )
    p.add_argument(
        "--idle-seconds",
        type=float,
        default=0.0,
        help="Sleep this many seconds before the first generate_content (default: 0)",
    )
    p.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Run this many sequential generate_content calls (default: 1)",
    )
    args = p.parse_args()
    if args.repeat < 1:
        print("--repeat must be >= 1", file=sys.stderr)
        sys.exit(2)

    elapsed, status = probe_network()
    print(f"network_probe_https_s={elapsed:.3f} status={status} url={GEMINI_API_HOST}")

    if args.probe_only:
        return

    settings = get_settings()
    if not (settings.gemini_api_key and str(settings.gemini_api_key).strip()):
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    timeout_ms = max(1, int(float(settings.gemini_http_timeout_seconds) * 1000))
    tb = int(settings.gemini_thinking_budget)
    retry_attempts = settings.gemini_http_retry_attempts
    http_kw: dict[str, object] = {"timeout": timeout_ms}
    if retry_attempts is not None:
        http_kw["retry_options"] = types.HttpRetryOptions(attempts=max(1, int(retry_attempts)))

    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(**http_kw),
    )
    model = settings.gemini_model
    prompt = (
        "Extract tasks from: '@Đỗ: update NDA contract asap, deadline là trước thứ Sáu này.'"
    )
    config = types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=1024,
        system_instruction="Return JSON only.",
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_budget=tb),
    )
    print(
        f"model={model} thinking_budget={tb} timeout_ms={timeout_ms} "
        f"http_retry_attempts={retry_attempts if retry_attempts is not None else 'sdk_default'}"
    )

    if args.idle_seconds > 0:
        print(f"idle_sleep_s={args.idle_seconds:.1f}")
        time.sleep(args.idle_seconds)

    for i in range(args.repeat):
        gen_elapsed, text = run_once(client, model, prompt, config)
        print(f"call={i + 1}/{args.repeat} latency_s={gen_elapsed:.2f}")
        if i == 0:
            print(text[:400])


if __name__ == "__main__":
    main()
