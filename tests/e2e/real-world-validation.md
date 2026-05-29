# Real-World Validation — Gmail Dogfooding (Honest Scope)

**First sync:** 2026-05-23 · **Controlled dogfood + diagnosis + pinned re-measure:** 2026-05-26 → 2026-05-28
**Account:** primary author inbox (single real Google account)
**Purpose:** record what TaskBot was validated on against *real* email versus
*synthetic enterprise* data, so the thesis claims match the evidence exactly —
including the diagnostic arc that took an alarming first dogfood result
(58% deadline accuracy, 4/10 high-confidence emails missed) and root-caused it
to **provider-fallback contamination** plus a deterministic **drop amplifier** in
`normalize_tasks`, both of which are now addressed (§5).

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

## 5. Controlled 20-email dogfood + provider-fallback diagnosis (2026-05-26 → 28)

A controlled 20-email batch (10 high-confidence + 10 mixed-noise; payloads at
`tools/gmail-test-sender/fixtures/`) was sent to the dogfood Gmail account and
processed by the live sync. The first pass surfaced a striking pattern: 18 tasks
created, **4 high-confidence emails produced zero tasks**, and **5 explicit
deadlines resolved wrong** (typically collapsing near the received date). The
synthetic eval scored 0.901 Deadline Exact on the same pipeline, so the gap
demanded an honest diagnosis, not a hand-wave.

### 5.1 Diagnostic arc — what was actually broken

1. **All 20 emails were synced.** `source_documents` count = 20; every
   `pipeline_runs.status='completed'` with no `error_message`. Neither sync
   coverage nor a transient error explains the 4 missing tasks.
2. **Replay (`agent/scripts/replay_dogfood_diag.py`) showed the symptoms were
   non-deterministic** — three runs on identical input gave three different
   outcomes (correct, wrong-deadline, silent-loss). Conclusion: the failure was
   **LLM non-determinism**, not a deterministic prompt or resolver bug.
   `temporal_resolve.py` was specifically exonerated — when the LLM emits a
   well-formed `deadline_v2`, "Friday, 20 June 2026"→06-20, VN "ngày 12/06/2026"
   →06-12, and "Monday 16/06/2026"→06-16 all resolve correctly.
3. **Smoking gun:** the replay terminated with
   `google.genai.errors.ServerError: 503 UNAVAILABLE` **on Gemini** — the
   *last-resort* fallback. The provider chain is Cerebras → Groq → Gemini, so
   reaching Gemini means both upper tiers were unavailable for that call.
4. **A deterministic amplifier was hiding underneath.**
   `normalize_tasks._normalize_task` returned `None` (discarding the entire
   task) whenever `_coerce_deadline_v2` returned `None` — i.e., whenever the LLM
   omitted the `deadline_v2` wrapper or emitted one missing `confidence`. A
   weaker fallback model is much more likely to produce that shape, so an LLM
   hiccup on one optional field became 100% task loss. **Fixed** in commit
   `ef93c67` (see `agent/app/pipeline/nodes/normalize_tasks.py:_empty_deadline_v2`):
   a valid-title task with missing/unsalvageable `deadline_v2` is now kept with
   `deadline=None` and `type='none'`, surfacing as a pending item flagged
   "Missing: deadline" — visible degradation instead of silent loss. Three
   existing unit tests that encoded the old "drop the whole task" policy were
   rewritten to assert the new contract; a new test guards the legitimate
   title-invalid drop. Full gate: **462 tests pass**.

### 5.2 Provider-pinned variance measurement (N=5, Cerebras-only)

Repeating the run with `EVAL_CEREBRAS_ONLY=1`
(`agent/scripts/measure_extraction_variance.py`) eliminates fallback
contamination and measures what the *primary* model alone produces. The
pipeline already records per-call provenance (`CallRecord{model, is_fallback,
rate_limited}`), so the pinning is verifiable, not asserted:

```
provenance: 155 LLM calls · 0 fallback fires · 0 rate-limit hits
            models used: gpt-oss-120b × 155  (100% Cerebras)
```

| metric | unpinned (full chain) | pinned (Cerebras only) |
|---|---|---|
| Deadline-exact among produced tasks | mixed (5 wrong / 12 in first dogfood) | **100% across every email** |
| Silent drops / 100 runs (post-fix) | 0 | **0** |
| `nm01` "No action needed" false-positive | 100% | **0%** |
| `nm07` newsletter false-positive | 0% | 0% |
| `nm02` / `nm03` vague-soft-ask false-positive | 60–100% | **100% — genuinely borderline** |
| Cerebras-only extraction wobble | — | most 100%; hc01/hc05 80%, hc10 60% |

Two cells deserve honest call-outs. **`hc03` extracts zero tasks in 3/3 pinned
verification runs** (3 LLM calls per run — the extract-retry pattern firing on
empty output): Cerebras has a **reproducible blind spot on hc03's structured
`Owner:/Due:/Deliverable:/Steps:` format**. In production the fallback chain
rescues hc03 — Groq or Gemini extracts what Cerebras misses. So fallback is not
purely "weaker quality": for some inputs it is the recovery mechanism. The
graceful-degradation fix in §5.1 handles both directions: weaker-model outputs
no longer destroy tasks, *and* primary-model misses get a second chance via the
chain. `hc02` extracts identically and correctly in targeted verification
(3/3 runs, deadline 2026-06-12) but only 1/5 in the larger measurement window —
an unresolved sampling wobble worth noting but not over-interpreting.

### 5.3 What this means for the thesis claims

> **Correction (2026-05-29):** the original wording of this section ("`temporal_resolve.py`
> and the extraction prompt are confirmed clean") was based on the §5.2 pinned
> measurement which turned out to have a measurement artifact — see §5.4. The
> resolver in fact had a deterministic override bug that the measurement script
> happened to bypass. The corrected claim is preserved below for honesty about
> the diagnostic arc.

- **Provider-fallback is one degradation cause, not the only one.** Pinning to
  Cerebras eliminates fallback contamination (verified end-to-end: 33/33 calls
  during the post-fix re-sync hit Cerebras, 0 fallback). But pinning alone did
  **not** restore deadline accuracy on the original 7 problem emails — see §5.4
  for the second cause and its fix.
- **Production extraction quality is bounded by the weakest model in the active
  chain.** This is Rule 4's prophecy (eval strict mode forbids fallback) now
  observed in production. Two operational stances are defensible: pin to the
  SLA primary and fail-closed on outage, **or** keep the chain for availability
  and rely on the per-call provenance for auditability.
- **Abstention on FYI mail is fine on the primary model** (`nm01` recovers from
  100%→0% false-positive when fallback is excluded). The over-extraction on
  vague soft asks (`nm02`/`nm03`) is the **real, isolated** auto-confirm-gate
  work — deferred to future work pending threshold-sweep evidence (policy
  Rule 2), but now properly scoped instead of conflated with fallback noise.

The diagnostic and measurement scripts are committed at
`agent/scripts/replay_dogfood_diag.py` and
`agent/scripts/measure_extraction_variance.py` so any reviewer can reproduce
the arc.

### 5.4 Resolver-level override bug (2026-05-29 production re-sync)

After Layer 1+2 (provider pinning + retry-with-backoff, `LLM_STRICT_PRIMARY=cerebras`)
was deployed, a fresh dogfood re-sync was expected to deliver the
pinned-measurement quality (§5.2: 100% deadline-exact) on the live pipeline.
It did not. Provider mix was clean — 33 calls Cerebras, 0 fallback — yet
**7 of 13 deadline-bearing emails still resolved wrong**, on exactly the same
formats and the same off-by-many-days "next-weekday-after-anchor" pattern that
had been blamed on fallback contamination.

Targeted replay with **production-shaped state** (`metadata={"sent_at": "2026-05-23T..."}`
mirroring what Gmail sync provides — script:
`agent/scripts/targeted_replay_resolver_check.py`) dumped the intermediate
`deadline_v2` shape pre- and post-resolver:

| email | LLM-emitted | post-resolver | verdict |
|---|---|---|---|
| Beta slides (`"Friday, 20 June 2026"`) | `phrase_class='absolute'`, `iso='2026-06-20'` | `iso='2026-05-29'` | resolver overrode by next-Friday-after-anchor |
| Henderson (`"Tuesday, 10 June 2026"`) | `'absolute'`, `'2026-06-10'` | `'2026-05-26'` | resolver overrode by next-Tuesday-after-anchor |
| Confirm receipt (`"Monday 9 June"`) | `'absolute'`, `'2026-06-09'` | `'2026-05-25'` | resolver overrode by next-Monday-after-anchor |
| Acme vendor (`"trước 09:00 ngày 16/06/2026"`) | `'absolute'`, `'2026-06-16'` | `'2026-05-23'` (=anchor) | resolver matched `(\d+)\s*ngày` on the time-prefix `"00 ngày"` and returned `anchor + 0 days` |

**The pinned measurement masked this.** `measure_extraction_variance.py` built
its state with `metadata={}` → `sent_at=None` → `anchor=None`, and
`enrich_deadline_v2_with_symbolic_iso` returns early when `anchor is None`. The
V1 fallback path (where the weekday-consistency gate and VN `"(\d+)\s*ngày"`
detector live) therefore **never ran during the measurement** — only the LLM's
emitted ISO survived, which is correct. Production has `anchor` populated from
the Gmail message's sent date, so the V1 path runs and overrides.

Two distinct override bugs were firing on the same emails:

1. **Weekday-consistency gate** triggered when the source text contains a
   weekday label that disagrees with the actual day-of-week of the emitted
   iso. The fixture-author had written `"Friday, 20 June 2026"` but
   2026-06-20 is a Saturday — and the same is true for the Henderson
   "Tuesday 10 June" (actually a Wednesday) and Confirm receipt "Monday 9
   June" (actually a Tuesday). The gate dutifully "corrected" the iso to
   the next instance of the labelled weekday after the anchor, producing
   a date weeks in the past. This same failure mode applies to any real
   email where the writer mislabels the weekday — common in informal
   English correspondence.
2. **VN closed-set detector** matched `(\d+)\s*ngày` against the substring
   `"00 ngày"` of `"trước 09:00 ngày 16/06/2026"` — i.e. the `00` of the
   time prefix `09:00` followed immediately by ` ngày`. With no word-boundary
   isolation between time and date, the regex returned `n=0` and
   `anchor + 0` days.

Both gates were originally designed for **v1-style output (no `phrase_class`)**
and rescue legitimate LLM arithmetic errors — see existing tests
`test_weekday_gate_corrects_iso_off_by_one_{vi,en}` and
`test_non_weekday_symbolic_gate_corrects_existing_iso_for_{tomorrow,n_days}`.
None of those tests set `phrase_class`. The v2 contract says: when the LLM
emits `phrase_class="absolute"`, it is asserting "this is a fully-resolved
calendar date, no symbolic interpretation needed." The fix respects that
contract surgically:

```python
# agent/app/pipeline/temporal_resolve.py — added before the V2/V1 dispatch
if phrase_class == "absolute" and existing_iso:
    return out
```

`existing_iso` has already passed the plausibility gate (≤ `_MAX_FUTURE_DAYS`
from anchor) earlier in the function. An implausible iso is nulled there, so
this short-circuit only fires for trusted absolutes. The 6 new tests in
`test_temporal_resolve.py` cover each replay case as a regression fixture plus
two negative guards (implausible iso still nulled; absent iso still falls
through to V1 rescue for `phrase_class='absolute'`-with-text-only output).

**Verified on real Gmail re-sync (2026-05-29 13:21–13:26).** Wiped dogfood
account, agent restarted with both Layer 1+2 and the resolver short-circuit
live, scheduler re-synced the same 20 emails:

| | before fix | after fix |
|---|---|---|
| Beta slides (`Friday 20 June`) | 2026-05-29 | **2026-06-20** ✅ |
| Henderson draft (`Tuesday 10 June`) | 2026-05-26 | **2026-06-10** ✅ |
| Confirm receipt (`Monday 9 June`) | 2026-06-01 | **2026-06-09** ✅ |
| Acme vendor (VN time-prefix) | 2026-05-26 | **2026-06-16** ✅ |
| Interview synthesis (`Wednesday 25 June`) | 2026-05-27 | **2026-06-25** ✅ |
| Compile market research Q2 | 2026-05-26 | **2026-06-12** ✅ |
| Q2 compliance reassignment (`Monday 16/06`) | 2026-06-01 | **2026-06-16** ✅ |
| **Subtotal** | **7/13 wrong** | **0/13 wrong** |
| Provider mix during sync | (n/a — pre-Layer 1+2 sync) | 33/33 Cerebras, 0 fallback |
| Regressions on the 6 previously-correct deadlines | — | **0** |
| Full test gate | 462 pass (pre this work) | **478 pass** (+10 Cerebras strict, +6 resolver short-circuit) |

The `hc10` deploy-hotfix blind spot (Limitation #4 in §7) is unchanged:
Cerebras still does not emit a `deadline_v2` for the `Owner:/Due:/Deliverable:/
Steps:` structured format. With graceful degradation (§5.1), the task surfaces
as a pending item with `deadline=None` rather than disappearing.

### 5.5 Methodology note for the thesis defence

The arc from §5.1 → §5.4 is the single most useful lesson of the project:

- **Synthetic eval (0.901 Deadline Exact) over-claimed.** The 250-sample eval
  generated its `sent_at` field synthetically and uniformly — its anchor was
  always set, but the LLM rarely emitted `phrase_class='absolute'` on the
  generated phrasings, so the V1 fallback rescues did most of the work in
  production-shaped configurations. The eval never exercised the
  absolute-with-text-weekday-mismatch case that real human writing produces.
- **Pinned variance measurement (100% Deadline Exact) over-claimed too.**
  Its `metadata={}` shortcut, intended only to avoid plumbing anchor through
  the harness, in fact bypassed the resolver entirely. The measurement scored
  the LLM's raw emission, not the system's resolved output.
- **The real-world dogfood was the first configuration where the LLM, the
  resolver, and a realistic anchor all ran together on natural-shape text.**
  That is when the bug showed up. The fix is structurally simple (one
  conditional, ~30 lines including the docstring) but only *findable* via this
  arc.

For the defence: this is the kind of finding that strengthens rather than
weakens the project — measurement infrastructure can mask production bugs as
effectively as expose them, and the discipline of refusing to declare "done"
until real-world dogfood agrees is what surfaced both the provider-fallback
issue and the resolver override. The two fixes (Cerebras strict mode in
§5.1/§5.2 lineage, resolver short-circuit in §5.4) are independent and both
contribute. The combination is what the production system needs.

### 5.6 Calendar dispatch architecture — MCP → direct REST pivot (2026-05-30)

After the deadline-extraction bugs were closed out, end-to-end verification on
the same dogfood account exposed a third independent issue: **0 of 19
confirmed tasks** had `calendar_event_id` populated, and **0 calls** to the
calendar dispatch endpoint were visible in agent logs. Direct invocation of
`async_dispatch_notifications` against a real OAuth token returned `HTTP 404
Page not found` from the configured MCP endpoint
`https://gcal.mcp.claude.com/mcp`. The pipeline's `try/except` wrapper kept
the run alive and the dispatch errors went into `state["errors"]` but did not
propagate to `pipeline_runs.error_message`, so the failure was invisible at
the DB-run level — a silent runtime gap behind passing unit/E2E tests, which
mocked the dispatch.

**Decision: pivot from the MCP shim to direct Google Calendar REST v3 via
`httpx`.** Three considerations made this the smaller change:

- The MCP endpoint is dead and not under our control to fix.
- `google-api-python-client` was not installed in the agent image; adding it
  would introduce a new auth pattern (`google.oauth2.credentials.Credentials`)
  that diverges from the rest of the codebase.
- `httpx.AsyncClient` is already the agent's standard HTTP layer (used by
  every other MCP client), and Google Calendar's REST API accepts the same
  OAuth bearer token already issued for Gmail and Drive sync.

**Implementation:** `agent/app/mcp/calendar_client.py` was rewritten to
`POST`/`PATCH` directly against
`https://www.googleapis.com/calendar/v3/calendars/primary/events`. The class
name `CalendarMCPClient` was deliberately preserved — `notification_service`,
the calendar-resync queue worker in `queue_consumer.py`, and four existing
mock tests all reference it by that name; renaming would force test churn for
zero behavioural gain. `create_event`/`update_event` signatures were kept
identical so callers are unchanged. Error semantics are preserved by
embedding the status code in the `RuntimeError` message
(`"Google Calendar {op} failed [{status}]: {body}"`) — the existing
`"403" in str(exc)` detector in `notification_service` and the
auth-revoked-or-403 check in `_process_calendar_resync_job` continue to work
without modification.

**All-day events.** `tasks.deadline` is stored as `DATE` (no time component),
so every event is sent as all-day. Google Calendar's all-day contract uses
an *exclusive* end date, so a deadline of 2026-06-20 becomes
`start={"date":"2026-06-20"}`, `end={"date":"2026-06-21"}`. Time-of-day
extraction (e.g. "5 PM ICT") and timezone normalisation are documented as
future work in §7.

**OAuth scopes** already included `https://www.googleapis.com/auth/calendar.events`
in the `SCOPES` list (`backend/app/services/auth_service.py:26`), and the
dogfood user's token had been issued with that scope, so no consent flow
change or re-login was required.

**Verified end-to-end on 2026-05-30.** Mass-dispatched the 13
confirmed-with-deadline tasks from the post-fix dogfood — 13 real Google
Calendar events created, 0 errors, all `calendar_event_id` and
`notification_sent` columns populated. A second pass re-dispatching the same
task IDs exercised the `update_event` (PATCH) path — also 13/13 successful,
confirming the idempotent re-dispatch / calendar-resync flow used by
`_process_calendar_resync_job` after a conflict merge. The 6 confirmed
tasks **without** events all lacked deadlines — those are correctly routed
to the `in_app_reminder` path by `notification_service`, not skipped.

**Unit tests** (`agent/tests/unit/test_calendar_client_direct_api.py`,
+8 tests): all-day body shape, exclusive-end-date contract including month
and year boundaries, bearer-header presence, error-message status-code
embedding for the 403/401 detectors, response-id fallback. Full gate after
this change: **486 pass** (was 478; +8), 0 regressions, no changes to
`notification_service.py` or any other caller.

---

## 6. Cross-reference: scaled extraction quality

The real-inbox extraction in §2 is the qualitative complement to the quantitative
250-sample evaluation:

- **89.6% Fully Correct · 0.901 Deadline Exact** (corrected artifact)
- Title F1 0.974 · Assignee F1 0.975 · Conflict F1 0.889 (precision 1.0) · ECE unchanged
- Artifact: `tests/eval/policy_freeze/corrected_250_final.json` (+ report)

Together: the eval shows the extraction is accurate at scale on representative
synthetic enterprise data; the dogfooding (§2) shows it transfers to real,
unseen, noisy email; §5 isolates the production-time degradation cause; and the
automated hero tests (§4) show the enterprise features are wired correctly
end-to-end.

---

## 7. Honest limitations (for the Future Work chapter)

1. **Single real account, single platform.** Real validation used one Gmail
   account with no connected Drive, so cross-platform multi-source conflict was
   not exercised on real data.
2. **Low real task-bearing volume.** A noise-heavy personal inbox cannot
   demonstrate auto-confirm or thread reassignment at the rate an enterprise
   team inbox would. These are synthetic-validated.
3. **No multi-week longitudinal run.** Dogfooding was a point-in-time sync, not
   a sustained deployment; drift, retraction rates over time, and notification
   fatigue are not measured.
4. **Primary-model blind spot (`hc03`).** Cerebras `gpt-oss-120b` deterministically
   refuses to extract tasks from at least one structured email format
   (`Owner:/Due:/Deliverable:/Steps:`). In production the fallback chain
   recovers it; this is a single observed case, not a systematic study.
5. **Auto-confirm gate on borderline soft asks** (`nm02`/`nm03`-style)
   over-extracts on the primary model itself. Fixing this needs a policy
   threshold sweep (Rule 2) on a larger labelled real-noise corpus.
6. **Future work:** deploy to a real enterprise team (the Anna persona — Tech
   Lead, team of 8) to validate auto-confirm precision, thread-update detection,
   and multi-source conflict on real cross-platform, multi-author traffic; and
   measure single-pass vs. self-consistency vs. provider-pinned strategies
   side-by-side on a multi-week longitudinal trace.
