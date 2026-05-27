# Real-World Validation — Gmail Dogfooding (Honest Scope)

**Date:** 2026-05-23 · **Account:** primary author inbox (single real Google account)
**Purpose:** record what TaskBot was validated on against *real* email versus
*synthetic enterprise* data, so the thesis claims match the evidence exactly.

> **One-line framing for the defense:**
> Task **extraction** and **abstention** are validated on a real, mixed Gmail
> inbox. **Auto-confirm** and **multi-source / thread-update conflict detection**
> are validated on representative synthetic enterprise data, because the real
> inbox lacks the volume of high-confidence work tasks and thread reassignments
> those features target. Real-world validation of those advanced features is
> documented as future work (enterprise team deployment).

This is deliberately *not* an over-claim. Distinguishing real signal from
synthetic seed data is itself part of the evaluation-integrity story (see the
Phase 9 forensic in the eval artifacts).

---

## 1. Inbox composition (what the real account actually contains)

The author's inbox is a **mixed personal inbox**, not an enterprise work queue.
Approximate composition over the synced window:

| Category | Examples | Task-bearing? |
|----------|----------|---------------|
| Recruitment / HR | interview-schedule confirmations, "Test Fresher 2026" invites, document-prep requests | **Yes** — explicit asks + deadlines |
| Newsletters | The Batch (DeepLearning.AI), Google I/O, product announcements | No — informational |
| Job alerts | TopCV, VietnamWorks, LinkedIn job digests | No — noise |
| Notifications / receipts | Google Play receipts, LinkedIn Premium notices | No |

Implication: the genuine task-bearing volume is **recruitment/HR email**, with
the bulk of the inbox being noise. That makes the inbox an excellent stress test
for **abstention**, and a fair (if low-volume) test for **extraction** — but a
poor source for high-confidence *work* tasks and multi-party *thread
reassignments*, which is what auto-confirm and conflict detection are built for.

---

## 2. Validated on REAL Gmail

### 2.1 Extraction — VALIDATED
TaskBot correctly extracted actionable tasks from real recruitment/HR emails,
including correct deadline parsing:

| Extracted task (real) | Deadline | Source |
|-----------------------|----------|--------|
| Phản hồi email xác nhận lịch phỏng vấn | 13/05 | HR interview email |
| Xác nhận tham gia Test Fresher 2026 | 07/05 | Recruitment email |
| Chuẩn bị hồ sơ nhân sự | — | HR onboarding email |
| Điền thông tin cá nhân | — | HR form-request email |

These are real-sync rows (not seed data). They demonstrate the
parse → extract → normalize → validate chain working on unseen, real Vietnamese
email with real temporal expressions.

### 2.2 Abstention — VALIDATED
Newsletters, job alerts, and notifications were **correctly NOT turned into
tasks**. On a noise-heavy inbox this is the more important property: the system
does not manufacture work from informational mail. This is the real-world
counterpart to the dataset's no-task / abstain samples.

---

## 3. Validated on SYNTHETIC enterprise data (NOT real sync)

The following dashboard items are **synthetic seed data**, used because the real
inbox does not contain comparable cases. They must be labelled as such in any
screenshot used for the defense:

- **Auto-confirmed tasks** — e.g. "Hương revise UI/UX", "Minh Đức fix bug",
  "Lan gửi quote" (carry the "Auto" chip). High-confidence work tasks with a
  clear owner/deadline; the real inbox produced too few of these to exercise
  auto-confirm meaningfully.
- **Thread-update conflict** — e.g. "Submit Q2 compliance report" (reassigned +
  deadline moved). The real inbox contained no multi-message thread with a
  reassignment, so thread-update detection is shown on a synthetic thread.
- **Multi-source conflict** — Gmail-vs-Drive same-deliverable mismatch. Requires
  two connected platforms describing the same task; not present in the real
  single-platform sync window.

Why this is acceptable evidence: each of these features is **deterministically
and reproducibly tested** (see §4), and the extraction quality that feeds them
is independently validated at scale (250-sample eval, §5) and on real email
(§2). The synthetic cases isolate the *feature logic* on inputs of the exact
shape it was designed for.

---

## 4. Automated, reproducible coverage (committed)

The hero scenarios are covered by deterministic tests (no LLM quota, no live
account) so the behaviour is reproducible by any reviewer:

| Scenario | Test | What it proves |
|----------|------|----------------|
| Multi-source conflict (Gmail↔Drive) | `agent/tests/e2e/test_hero_scenarios.py::test_scenario1_*` | Real `validate_tasks` node feeds the cross-source loader's candidate into the detector and emits `scope="multi_source"`; same-platform candidate does **not**. |
| Smart auto-confirm | `agent/tests/e2e/test_hero_scenarios.py::test_scenario3_*` | A high-confidence doc, run through the real extract→normalize→validate→save chain, persists `status="confirmed"`, `confirmed_by="system"`; a low-confidence doc stays `pending`. |
| Thread-update merge + calendar resync | `backend/tests/integration/test_hero_merge_e2e.py` | Against **real Postgres**: survivor takes the reply's deadline, source is dismissed, conflict resolved, and a `calendar_resync` job is enqueued for the survivor; an assignee-only merge enqueues nothing. |

Manual, full-stack walkthroughs against a real account remain in
[`CHECKLIST.md`](./CHECKLIST.md) (Flows 1–7).

Run:

```bash
# Scenarios 1 & 3 — offline, deterministic
pytest agent/tests/e2e/test_hero_scenarios.py -v

# Scenario 2 — needs the dev Postgres (port 55432); auto-skips if unreachable
DATABASE_URL='postgresql+asyncpg://taskbot:taskbot@localhost:55432/taskbot' \
  pytest backend/tests/integration/test_hero_merge_e2e.py -v
```

---

## 5. Cross-reference: scaled extraction quality

The real-inbox extraction in §2 is the qualitative complement to the quantitative
250-sample evaluation:

- **89.6% Fully Correct · 0.901 Deadline Exact** (corrected artifact)
- Title F1 0.974 · Assignee F1 0.975 · Conflict F1 0.889 (precision 1.0) · ECE unchanged
- Artifact: `tests/eval/policy_freeze/corrected_250_final.json` (+ report)

Together: the eval shows the extraction is accurate at scale on representative
synthetic enterprise data; the dogfooding (§2) shows it transfers to real,
unseen, noisy email; and the automated hero tests (§4) show the enterprise
features are wired correctly end-to-end.

---

## 6. Honest limitations (for the Future Work chapter)

1. **Single real account, single platform.** Real validation used one Gmail
   account with no connected Drive, so cross-platform multi-source conflict was
   not exercised on real data.
2. **Low real task-bearing volume.** A noise-heavy personal inbox cannot
   demonstrate auto-confirm or thread reassignment at the rate an enterprise
   team inbox would. These are synthetic-validated.
3. **No multi-week longitudinal run.** Dogfooding was a point-in-time sync, not
   a sustained deployment; drift, retraction rates over time, and notification
   fatigue are not measured.
4. **Future work:** deploy to a real enterprise team (the Anna persona — Tech
   Lead, team of 8) to validate auto-confirm precision, thread-update detection,
   and multi-source conflict on real cross-platform, multi-author traffic.
