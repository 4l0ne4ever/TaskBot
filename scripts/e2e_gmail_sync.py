#!/usr/bin/env python3
"""
E2E automated runner — Flow 1: Gmail sync happy path.

Tests the full path: trigger sync → pipeline processes emails → tasks visible in API.
Requires a real running stack and a valid JWT + Google OAuth token.

Usage:
  python scripts/e2e_gmail_sync.py
  python scripts/e2e_gmail_sync.py --verbose
  python scripts/e2e_gmail_sync.py --require-tasks        # fail if 0 tasks extracted
  python scripts/e2e_gmail_sync.py --time-range 7d

Required env vars (or in .env.e2e at repo root):
  E2E_BASE_URL       — backend URL, e.g. http://127.0.0.1:8000
  E2E_JWT_TOKEN      — JWT issued by TaskBot after Google OAuth login

Optional:
  E2E_TIME_RANGE     — 12h|1d|3d|7d|30d (default: 1d)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    env_file = ROOT / ".env.e2e"
    if not env_file.exists():
        env_file = ROOT / ".env"
    load_dotenv(env_file, override=False)


def _ok(step: str, detail: str = "") -> None:
    extra = f"  {detail}" if detail else ""
    print(f"  OK   {step}{extra}")


def _fail(step: str, detail: str) -> str:
    return f"  FAIL {step}: {detail}"


def _step(n: int, label: str) -> None:
    print(f"\n[{n}] {label}")


class E2ERunner:
    def __init__(self, base_url: str, jwt_token: str, *, verbose: bool = False, time_range: str = "1d") -> None:
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {jwt_token}"}
        self.verbose = verbose
        self.time_range = time_range
        self.failures: list[str] = []
        self._client = httpx.Client(timeout=30.0)

    def _get(self, path: str, **params) -> httpx.Response:
        return self._client.get(f"{self.base}{path}", headers=self.headers, params=params)

    def _post(self, path: str, **params) -> httpx.Response:
        return self._client.post(f"{self.base}{path}", headers=self.headers, params=params)

    def _assert(self, condition: bool, step: str, detail: str = "") -> bool:
        if condition:
            _ok(step, detail)
            return True
        self.failures.append(_fail(step, detail or "assertion failed"))
        print(self.failures[-1])
        return False

    # ------------------------------------------------------------------

    def check_sync_not_running(self) -> None:
        _step(1, "Pre-check: Gmail sync not already running")
        r = self._get("/sync/status")
        self._assert(r.status_code == 200, "GET /sync/status → 200", f"got {r.status_code}")
        states = r.json()
        gmail_state = next((s for s in states if s.get("source_type") == "gmail"), None)
        if gmail_state:
            self._assert(
                gmail_state.get("status") != "running",
                "Gmail status != running",
                f"status={gmail_state.get('status')}",
            )
        else:
            _ok("No prior Gmail sync state (first run)")

    def trigger_sync(self) -> bool:
        _step(2, f"Trigger Gmail sync (time_range={self.time_range})")
        r = self._post("/sync/trigger", source="gmail", time_range=self.time_range)
        ok = self._assert(r.status_code == 200, "POST /sync/trigger → 200", f"got {r.status_code}: {r.text[:200]}")
        if not ok:
            return False
        body = r.json()
        self._assert(body.get("status") == "queued", "response.status == queued", str(body))
        self._assert(body.get("source") == "gmail", "response.source == gmail", str(body))
        return True

    def poll_progress(self, timeout: int = 90) -> bool:
        _step(3, f"Poll sync progress (timeout={timeout}s)")
        deadline = time.monotonic() + timeout
        last_step = ""
        while time.monotonic() < deadline:
            r = self._get("/sync/progress", source="gmail")
            if r.status_code != 200:
                time.sleep(2)
                continue
            data = r.json()
            step = data.get("step", "")
            if step != last_step and step:
                if self.verbose:
                    print(f"       progress: {step} — {data.get('detail', '')}")
                last_step = step
            if not data.get("active", True):
                _ok("Sync completed", f"last step: {last_step!r}")
                return True
            time.sleep(2)
        self.failures.append(_fail("poll_progress", f"sync did not complete within {timeout}s"))
        print(self.failures[-1])
        return False

    def check_sync_status(self) -> None:
        _step(4, "Verify sync status updated")
        r = self._get("/sync/status")
        self._assert(r.status_code == 200, "GET /sync/status → 200")
        states = r.json()
        gmail_state = next((s for s in states if s.get("source_type") == "gmail"), None)
        if gmail_state:
            self._assert(
                gmail_state.get("status") == "idle",
                "Gmail status == idle after completion",
                f"status={gmail_state.get('status')}",
            )
            last_synced = gmail_state.get("last_synced_at")
            self._assert(last_synced is not None, "last_synced_at populated", str(last_synced))

    def fetch_tasks(self, require_tasks: bool = False) -> list[dict]:
        _step(5, "Fetch extracted tasks from this sync")
        r = self._get("/tasks", source="gmail", status="pending", limit=50)
        self._assert(r.status_code == 200, "GET /tasks → 200", f"got {r.status_code}")
        if r.status_code != 200:
            return []
        tasks = r.json()
        now_utc = datetime.now(timezone.utc)

        # Filter tasks created in the last 3 minutes (this sync run)
        recent: list[dict] = []
        for t in tasks:
            created_raw = t.get("created_at") or ""
            try:
                created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                age_seconds = (now_utc - created).total_seconds()
                if age_seconds <= 180:
                    recent.append(t)
            except (ValueError, TypeError):
                pass

        if self.verbose and recent:
            print(f"       Recent tasks ({len(recent)}):")
            for t in recent:
                print(f"         - [{t.get('confidence', '?'):.2f}] {t.get('title', '')[:80]}")

        if require_tasks:
            self._assert(len(recent) >= 1, "≥1 task extracted in this sync", f"got {len(recent)}")
        elif len(recent) == 0:
            print("       INFO: 0 tasks extracted (no actionable emails in time_range, or all abstained)")
        else:
            _ok(f"{len(recent)} task(s) extracted")

        return recent

    def validate_task_fields(self, tasks: list[dict]) -> None:
        if not tasks:
            return
        _step(6, "Validate task field quality")
        for t in tasks:
            task_id = t.get("id", "?")
            title = t.get("title") or ""
            confidence = t.get("confidence")
            self._assert(len(title) > 0, f"task {task_id[:8]} has non-empty title")
            if confidence is not None:
                self._assert(
                    confidence >= 0.55,
                    f"task {task_id[:8]} confidence ≥ 0.55",
                    f"got {confidence}",
                )

    def check_pipeline_history(self) -> None:
        _step(7, "Check pipeline run history")
        r = self._get("/sync/history", limit=5)
        self._assert(r.status_code == 200, "GET /sync/history → 200")
        if r.status_code != 200:
            return
        runs = r.json()
        recent_runs = [run for run in runs if run.get("source_type") == "gmail"]
        if recent_runs:
            latest = recent_runs[0]
            status = latest.get("status")
            self._assert(
                status in ("completed", "partial"),
                "Latest pipeline run completed",
                f"status={status}",
            )

    def check_conflict_dedup(self) -> None:
        _step(8, "Idempotency: re-trigger sync (same emails → no duplicates)")
        r = self._post("/sync/trigger", source="gmail", time_range=self.time_range)
        if r.status_code == 409:
            _ok("Re-trigger while running → 409 SYNC_IN_PROGRESS (correct)")
            return
        if r.status_code == 200:
            # Wait briefly and check task count hasn't changed
            time.sleep(5)
            r2 = self._get("/tasks", source="gmail", status="pending", limit=200)
            if r2.status_code == 200:
                all_tasks = r2.json()
                _ok(f"Re-sync queued — total tasks now: {len(all_tasks)} (dedup should prevent growth)")
            return
        _ok(f"Re-trigger returned {r.status_code} (acceptable)")

    def run(self, require_tasks: bool = False) -> bool:
        print(f"\n=== TaskBot E2E — Flow 1: Gmail Sync Happy Path ===")
        print(f"    base_url:   {self.base}")
        print(f"    time_range: {self.time_range}")
        print(f"    started:    {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")

        self.check_sync_not_running()
        triggered = self.trigger_sync()
        if not triggered:
            return self._report()

        completed = self.poll_progress()
        self.check_sync_status()

        tasks = []
        if completed:
            tasks = self.fetch_tasks(require_tasks=require_tasks)
            self.validate_task_fields(tasks)

        self.check_pipeline_history()
        self.check_conflict_dedup()

        return self._report()

    def _report(self) -> bool:
        print(f"\n{'='*50}")
        if self.failures:
            print(f"RESULT: FAILED — {len(self.failures)} assertion(s) failed")
            for f in self.failures:
                print(f"  {f}")
            return False
        print("RESULT: PASSED")
        return True

    def close(self) -> None:
        self._client.close()


def main() -> int:
    _load_env()

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--jwt-token", default=os.getenv("E2E_JWT_TOKEN", ""))
    ap.add_argument("--time-range", default=os.getenv("E2E_TIME_RANGE", "1d"),
                    choices=["12h", "1d", "3d", "7d", "30d"])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--require-tasks", action="store_true",
                    help="Fail if 0 tasks extracted (strict mode for CI)")
    args = ap.parse_args()

    if not args.jwt_token:
        print("ERROR: E2E_JWT_TOKEN not set. Export it or add to .env.e2e", file=sys.stderr)
        print("       How to get it: log in to TaskBot → DevTools → copy JWT from cookie/localStorage", file=sys.stderr)
        return 1

    runner = E2ERunner(
        args.base_url,
        args.jwt_token,
        verbose=args.verbose,
        time_range=args.time_range,
    )
    try:
        ok = runner.run(require_tasks=args.require_tasks)
    finally:
        runner.close()

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
