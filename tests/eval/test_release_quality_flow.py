from __future__ import annotations

import json
from pathlib import Path

import release_quality_flow


def test_load_freeze_thresholds_reads_chosen_values(tmp_path: Path) -> None:
    freeze = tmp_path / "chosen.json"
    freeze.write_text(
        json.dumps(
            {
                "status": "complete",
                "chosen": {
                    "confidence_abstain_threshold": 0.6,
                    "confidence_uncertain_threshold": 0.8,
                },
            }
        ),
        encoding="utf-8",
    )
    a, u = release_quality_flow._load_freeze_thresholds(freeze)
    assert a == 0.6
    assert u == 0.8


def test_load_freeze_thresholds_fails_when_missing(tmp_path: Path) -> None:
    freeze = tmp_path / "bad.json"
    freeze.write_text(json.dumps({"status": "complete", "chosen": {}}), encoding="utf-8")
    try:
        release_quality_flow._load_freeze_thresholds(freeze)
    except SystemExit as exc:
        assert "missing chosen thresholds" in str(exc)
    else:
        raise AssertionError("expected SystemExit for malformed freeze artifact")


def test_dry_run_invokes_all_stages(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, env: dict[str, str], dry_run: bool) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(release_quality_flow, "_run", _fake_run)
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        release_quality_flow.sys,
        "argv",
        [
            "release_quality_flow.py",
            "--dataset",
            str(dataset),
            "--dry-run",
            "--resume-sweep",
            "--skip-preflight",
        ],
    )
    rc = release_quality_flow.main()
    assert rc == 0
    assert len(calls) == 2
    assert calls[0][1].endswith("run_eval.py")
    assert calls[1][1].endswith("sweep_policy_thresholds_offline.py")
    assert "--result" in calls[1]


def test_dry_run_can_skip_baseline(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, env: dict[str, str], dry_run: bool) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(release_quality_flow, "_run", _fake_run)
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        release_quality_flow.sys,
        "argv",
        [
            "release_quality_flow.py",
            "--dataset",
            str(dataset),
            "--dry-run",
            "--skip-baseline",
            "--skip-preflight",
        ],
    )
    rc = release_quality_flow.main()
    assert rc == 0
    assert len(calls) == 2
    assert calls[0][1].endswith("run_eval.py")
    assert calls[1][1].endswith("sweep_policy_thresholds_offline.py")


def test_preflight_checks_missing_dataset_and_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(release_quality_flow, "_load_policy_keys", lambda: {"v1", "v2"})
    issues = release_quality_flow._preflight_checks(
        dataset=tmp_path / "missing.json",
        policy_version="v2",
        env={},
    )
    assert any("dataset not found" in it for it in issues)
    assert any("missing required env: GROQ_API_KEY" in it for it in issues)
    assert any("missing required env: DATABASE_URL" in it for it in issues)


def test_preflight_checks_reject_unknown_policy(monkeypatch, tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(release_quality_flow, "_load_policy_keys", lambda: {"v1", "v2"})
    issues = release_quality_flow._preflight_checks(
        dataset=dataset,
        policy_version="v9",
        env={"GROQ_API_KEY": "x", "DATABASE_URL": "postgresql://example"},
    )
    assert len(issues) == 1
    assert "unknown policy version" in issues[0]


def test_main_preflight_only_returns_zero(monkeypatch, tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(release_quality_flow, "_load_policy_keys", lambda: {"v1", "v2"})
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(
        release_quality_flow.sys,
        "argv",
        [
            "release_quality_flow.py",
            "--dataset",
            str(dataset),
            "--policy-version",
            "v2",
            "--preflight-only",
        ],
    )
    assert release_quality_flow.main() == 0


def test_dry_run_skips_freeze_validation_steps(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, env: dict[str, str], dry_run: bool) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(release_quality_flow, "_run", _fake_run)
    monkeypatch.setattr(release_quality_flow, "_load_policy_keys", lambda: {"v1", "v2"})
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(
        release_quality_flow.sys,
        "argv",
        [
            "release_quality_flow.py",
            "--dataset",
            str(dataset),
            "--dry-run",
            "--policy-version",
            "v2",
        ],
    )
    rc = release_quality_flow.main()
    assert rc == 0
    assert len(calls) == 2
    assert all("validate_freeze_artifact.py" not in " ".join(c) for c in calls)


def test_dry_run_online_sweep_mode_keeps_resume_flag(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, env: dict[str, str], dry_run: bool) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(release_quality_flow, "_run", _fake_run)
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        release_quality_flow.sys,
        "argv",
        [
            "release_quality_flow.py",
            "--dataset",
            str(dataset),
            "--dry-run",
            "--skip-preflight",
            "--sweep-mode",
            "online",
            "--resume-sweep",
        ],
    )
    rc = release_quality_flow.main()
    assert rc == 0
    assert len(calls) == 2
    assert calls[1][1].endswith("sweep_policy_thresholds.py")
    assert "--resume" in calls[1]


def test_offline_mode_uses_recomputed_aligned_result_without_second_pipeline_eval(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *, env: dict[str, str], dry_run: bool) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(release_quality_flow, "_run", _fake_run)
    monkeypatch.setattr(release_quality_flow, "_load_policy_keys", lambda: {"v1", "v2"})
    monkeypatch.setattr(release_quality_flow, "_load_freeze_thresholds", lambda path: (0.55, 0.76))
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(
        release_quality_flow.sys,
        "argv",
        [
            "release_quality_flow.py",
            "--dataset",
            str(dataset),
            "--policy-version",
            "v2",
            "--aligned-output",
            str(tmp_path / "aligned.json"),
        ],
    )

    rc = release_quality_flow.main()

    assert rc == 0
    run_eval_calls = [c for c in calls if c[1].endswith("run_eval.py")]
    assert len(run_eval_calls) == 1
    offline_calls = [c for c in calls if c[1].endswith("sweep_policy_thresholds_offline.py")]
    assert len(offline_calls) == 1
    assert "--write-aligned-result" in offline_calls[0]
    assert any(c[1].endswith("quality_gate.py") for c in calls)
