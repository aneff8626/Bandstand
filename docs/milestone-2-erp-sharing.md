# Milestone two: dependable ERP sharing

Branch `backend`, built on `app-edits`, which is Andrew's `codex/v0.3.0-alpha.1` plus four account and UI fixes.
Milestone one is included and re-verified on this base: 45 checks pass, 0 fail, 2 observed
(`docs/acceptance/accounts-local-20261017.md`).

## Status

"Local stack" is the Supabase CLI stack in Docker (real Auth, PostgREST and Postgres 17). It is not the cloud project.

| Deliverable | Implemented | Locally tested | Cloud tested | Hardware tested |
|---|---|---|---|---|
| Durable outbox: pending, uploading, uploaded, failed, withdrawn | yes | yes (unit + Q02–Q08) | no | n/a |
| Bounded exponential retry (30 s doubling to 1 h, 8 attempts) | yes | yes (unit + Q06) | no | n/a |
| Items bound to the consenting account; no upload under another account | yes | yes (unit mid-pass switch + Q07) | no | n/a |
| Server consent rechecked before every upload; withdrawal stops the queue at once, also offline | yes | yes (unit + Q04, Q05) | no | n/a |
| No backfill of earlier recordings after opting in | yes | yes (unit + Q01) | no | n/a |
| Restart reconciliation (interrupted upload resumes, stored once) | yes | yes (unit + Q08) | no | n/a |
| Partial-success handling when saving sharing settings | yes | code review only | no | n/a |
| Payload schema v2 (allowlisted metadata) | yes; **client still sends v1** | yes (unit + Q09) | no | n/a |
| Provisional quotas (100 new/day, 2,000 total; re-sends free) | yes | yes (Q11) | no | n/a |
| Malformed, oversized and text-bearing payloads refused | n/a | yes (Q09: 13 cases) | no | n/a |
| Deletion removes shared rows and the local queue | yes | yes (Q13) | no | n/a |
| Real recordings from a headset | n/a | no: synthetic fixtures | no | **no** |

## How it works now

- When a supported ERP run ends, the app queues it instead of uploading once and showing a toast on failure.
  Queueing needs the account's saved sharing choice (`erp_auto_share` and `erp_sharing_requested`).
- `erp_outbox.py` keeps one small JSON status file per recording in `<data>/erp-outbox/` (owner-only, written
  atomically). It holds the recording ID, the local session, the consenting user ID, the policy, the state,
  the attempt count, the next attempt time and a short error. **It never stores EEG.** The numeric payload is
  rebuilt from the local recording at upload time.
- A background thread starts with the desktop service and the preview server, and runs every 20 s or when
  woken. It takes the signed-in account and its token together and only processes that account's items.
  Before every upload it asks the server for current consent. Server consent decides; account metadata
  only records the person's intent.
  - Network errors, timeouts, 5xx, 401 and 429 count as transient: retry later.
  - Any other refusal (validation, consent, quota) marks the item failed. The person can retry it from
    Contribute to research.
- Withdrawing consent marks that account's queued items withdrawn locally before calling the server, so it
  holds when offline. Deleting shared copies remains a separate action, as the handoff asks.
- The Data Sharing dialog shows "Waiting to upload: N · Could not upload: M", recordings held for another
  account on this computer, and a Retry button. The Yes/No choice now reflects the server's consent record.
  If the consent save succeeds but the metadata or local save fails, the message says exactly what was
  saved.
- Sharing failures never block recording. The uploader catches everything, and an invalid `backend.json`
  disables the uploader instead of stopping the app.

## Schema v2: needs Andrew's decision before it is switched on

`bandstand-erp-v2` adds a `recording` object and per-channel `rejection` categories. Every value is a number
or comes from a fixed list:

| Field | Values |
|---|---|
| `app_version` | semantic version, e.g. `0.3.0-alpha.1` |
| `sample_rate_hz`, `units` | `256`, `uV` |
| `reference` | `FPz`, or `TP9-TP10-mean` for the reward task |
| `channels` | the analysed electrodes |
| `preprocessing`, `grid` | `causal-hp0.1-lp30-notch60q30`, `interpolated-256hz` |
| `epoch_s`, `baseline_s`, `analysis_window_s` | two numbers each |
| `trials_planned`, `trials_presented` | integers |
| `end` | `completed`, `stopped` or `interrupted` (stopped early is now explicit; early-stopped runs are still shared, now labelled) |
| `rejection` (per channel per trial) | subset of `missing`, `clipping`, `flatline`, `transient`, `blink`, `muscle`, `timing`, `other` |

The database accepts v1 and v2 from the new migration `20261017000001_erp_v2_and_quotas.sql`. The client keeps
sending v1 (`erp_sharing.SCHEMA`), because the current sharing notice does not mention these fields. To switch:

1. Replace the ERP sharing details text with something like: *"Shared data contain processed per-channel
   trial waveforms, trial condition numbers, relative sample times, which channels were rejected and why
   (category only, such as blink or muscle), and the recording settings: app version, filter settings,
   analysis windows, planned and presented trial counts, and whether the run was completed, stopped or
   interrupted. Continuous EEG, absolute recording times, custom labels, writing, embeddings and notes are
   excluded."*
2. Decide whether this is a new consent version (`erp-sharing-v2`) or covered by the current one.
3. Set `SCHEMA='bandstand-erp-v2'` in `erp_sharing.py`.

## Quotas and cost

- Provisional limits: 100 new recordings per account per 24 h, and 2,000 in total. Re-sending a stored
  recording is free.
- Per-request CPU is bounded by the API role's statement timeout (Supabase's default for `authenticated`
  is 8 s). Validating 1,000 trials × 2 channels × 257 samples (4.4 MB) took 0.7 s locally (Q12).
- The numbers need Andrew's judgement and measured cloud use. Request-rate limits beyond Auth's own are not
  implemented.

## Verification

- 140 Python tests pass, including 14 new outbox tests and 4 new schema tests. All JavaScript regression
  scripts pass. Release audit: 123 files, no findings.
- `scripts/staging_erp_sharing.py` on the local stack: 13/13. Full matrix: `docs/acceptance/erp-local-20261017.md`.
  It uses the real accounts module, real outbox and real RPCs, with two synthetic accounts and synthetic ERP
  fixtures. Text canaries are planted in titles, notes, condition labels and rejection wording, and none
  reached the database.
- The checks can fail. Removing the per-account filter in the outbox failed Q07 and the steps after it.
  Removing the mid-pass account check failed the unit test
  `test_account_switch_mid_pass_never_uploads_with_another_token`. The acceptance run cannot create that
  timing, so the unit test is the guard for it.
- `verify_permissions.sql`: 55/55 after the new migration.

## Not done, and production

- Nothing was applied to Andrew's cloud project. The new migration must follow the production procedure in
  the milestone-one report: inventory the schema, compare, then apply.
- No cloud or headset run. The fixtures stand in for engine output and claim `source: live` only inside the
  throwaway test directory, because the sharing gate requires it; the gate itself is unchanged.
- No researcher analysis or export path (the handoff lists one; it needs a decision about who may read
  pooled data), and no tamper-evident consent receipts. Both are next.
