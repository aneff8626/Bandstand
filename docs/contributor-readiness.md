# Contributor readiness and acceptance contract

This is a release gate, not a claim that every feature is finished. Unknown or untested means **not passed**. Record the exact commit, app version, macOS version, backend and test time with every result. The assistant mailbox is reserved for the final normal-user test; do not manually confirm, invite, whitelist or grant it privileges.

## 1. Nideesh can contribute

- [ ] Verify Nideesh's GitHub identity from PR #1 and grant repository collaborator access; invitation accepted.
- [ ] He can clone, create a branch, push, open a PR and review/merge under the agreed branch rules. Never share Andrew's signing key or production service-role key.
- [ ] Integration branch includes reviewed PR #1 and readiness fixes; clean diff and checks pass.
- [ ] Signed desktop development shell can run an editable checkout with real Bluetooth. Browser preview is for UI/simulated EEG; it cannot substitute for the native bridge.
- [ ] Development launch explicitly chooses a non-production backend and separate local data. Normal launch uses bundled code.
- [ ] A clean checkout can reproduce tests from documented prerequisites. Dependencies and public encoder are installed without participant archives.
- [ ] Staging uses synthetic participants only. Nideesh has the necessary staging access; production administration stays separate.

## 2. Install and startup

- [ ] Release contains an actual app archive, version, architecture, checksum and installation instructions, not only GitHub source archives.
- [ ] Developer ID signature verified; Gatekeeper accepts a downloaded/quarantined artifact on a clean supported Mac. Notarization/stapling verified before claiming frictionless installation.
- [ ] Drag/install into Applications, open once, startup screen appears without Terminal, Python or build tools.
- [ ] New installation shows sign-in/create-account/local-use choices; returning remembered account restores securely or explains that sign-in is needed.
- [ ] No password stored by Bandstand. Refresh token stays in Keychain; staging and production do not share its namespace.
- [ ] Bluetooth initialization has a visible waiting state, then connect/disconnect works; stop/start reconnect works without relaunch.
- [ ] Updating the signed app retains the same bundle identity and signing requirement. Test prior-version → candidate upgrade without resetting Accessibility/Input Monitoring/Bluetooth.
- [ ] Across-app typing works in Chrome/Google Docs and a native editor; secure input is excluded. UI counters and last-capture feedback update.

## 3. Normal-user signup (last, on the real release)

- [ ] Check exact backend identity, signup enabled, email confirmation enabled, custom SMTP and sender alignment; inspect logs without recording secrets.
- [ ] Using the reserved assistant email, submit signup through the app as an ordinary user. No admin-created user, manual confirmation, allowlist or special permissions.
- [ ] Receive real confirmation email, enter its code, reach main UI, save preferences, quit/reopen and recognize account.
- [ ] Wrong/expired code, resend cooldown, duplicate email, offline service and invalid password have clear feedback without leaking server payloads.
- [ ] Password recovery email arrives and works through the normal flow. Account deletion has an explicit confirmation and removes server-owned records; run destructive checks only on designated disposable staging accounts.
- [ ] Separate test proves an ordinary unrelated user can enroll; a successful SMTP API response alone is not delivery evidence.

## 4. ERP integration

- [ ] Ordered migrations installed and recorded in staging; fresh install and upgrade both pass.
- [ ] No consent → zero upload. Consent → one numeric, allowlisted recording; no writing, subject names, demographics or free-text answers.
- [ ] Outage/restart retries without duplicates; queue binds to the consenting account and cannot be sent by a different signed-in account.
- [ ] Withdrawal cancels pending work; server rejects uploads after revocation. Account A cannot read/update/delete B's data.
- [ ] Payload limits, quota errors, deletion and retry states tested. UI reports actual delivery, not merely preference saved.
- [ ] Production schema diff reviewed and backup/recovery plan recorded before migration; synthetic smoke record only.

## 5. Writing decoder and integrated learning

- [ ] Within-person model accumulates all eligible local sessions, with random held-out time blocks and boundary gaps preventing overlapping-window leakage.
- [ ] EEG, text, embeddings and individual unmasked gradients stay local. Tests plant canaries, inspect all outbound bodies and check filesystem publication boundaries.
- [ ] Shared model architecture, encoder revision, feature schema and preprocessing are versioned and identical across clients.
- [ ] Separate secure-aggregation coordinator deployed over TLS; Supabase stores auth, consent, round metadata and released aggregate models. Never use a Supabase table as an individual-gradient inbox.
- [ ] Authenticated cohort, dropout/replay protection, privacy accounting, poisoning strategy, model-signing trust and independent security review pass before enabling real contributions.
- [ ] Cross-user evaluation uses entirely held-out participants plus no-EEG baselines. Synthetic improvements do not establish real decoding performance.
- [ ] User can decline/withdraw. Policy explains model inversion risk, metadata visibility and inability to erase influence from already released aggregate models automatically.

## 6. Functional and performance acceptance

Run each activity from selection → setup → instructions → recording → stop/completion → results → reload saved results. Cover ERP visual/audio/images/flanker/reward, spectral tasks/custom conditions/public questions, personality questionnaires, reset/meditation, typing modes and artifact trainer. Disabled activities must say unavailable, not pretend to run.

For each: test missing headset, one bad channel, all bad channels, lost connection, Escape, repeated button clicks, resized window and long recording. Check channel-specific rejection, event timing, units, selected analysis range, sample counts and result provenance. Synthetic personality outputs must remain visibly synthetic.

Performance budgets to measure, not assume: 30-minute capture with no growing acquisition backlog; responsive typing and stop controls; stable memory after warmup; no silent data loss; phrase autosave survives app restart. Record CPU, RSS, queue lag, sample loss and disk growth. Real headset tests remain required after simulation passes.

## Assessment procedure

1. Run `python scripts/readiness.py` in an isolated environment. It runs Python and JavaScript tests and creates `.audit/readiness.json`. A missing runtime or failed suite fails the assessment.
2. Run `python scripts/audit_release.py` against the actual publication candidate. Review the allowlisted file manifest, secret-pattern scan and private-string comparison independently. Inspect git diff/staged filenames too; audit success covers its bundle, not arbitrary git history or binaries.
3. Perform the clean-Mac, staging two-account and production email tests above. Attach redacted evidence and commit/build IDs; never tokens, passwords, writing or raw EEG.
4. Mark separate outcomes: **developer collaboration ready**, **desktop pilot ready**, **ERP sharing ready**, **protected writing learning ready**. Do not collapse these into one green check.

## Initial evidence, 2026-10-19

Production dashboard reachable. User list showed two accounts, including Nideesh's university address; his reported Gmail address was absent. This does not establish why delivery failed or that signup now works. PR #1 reports synthetic/local backend tests, not live production or headset tests. Protected writing contributions remain disabled. New-user mailbox test has not been attempted.

## Findings added during this review

- Automated runner: Python discovery and all 17 JavaScript scripts passed with an isolated temporary data root. Real-data startup initially caused sandbox permission failures; the runner now prevents that by construction.
- Source publication audit: 148 allowlisted files; secret/path scan clear; compared 376 private strings with no matches. This is not a guarantee against every form of identifying data.
- Production SMTP: custom SMTP enabled, Gmail host/465 and matching sender/login; code-based signup template present. No setting change was saved. Real delivery remains unverified.
- October 17 email logs unavailable: free-plan retention is one day. No conclusion about the historical SMTP error can be drawn.
- Production consent, ERP and model-release tables have RLS enabled and no direct anon/authenticated SELECT grants. Full RPC/migration acceptance remains separate.
- GitHub collaborator management requires owner reauthentication; no invitation has been sent yet.
- Contributor native code compiles; release signing reached the existing Developer ID key and is awaiting macOS key access. Installed app was not replaced.

## Verified later in this run

- Ordinary production signup **passed** for the reserved assistant address: signup through `accounts.account`, real Gmail confirmation received, code verification, password sign-in and sign-out. Only the public client key was used; no admin API, manual confirmation, invitation, allowlist or account privilege changes. The password was generated in process memory and not retained. This tests the real app backend functions, not an entire click-through on a new Mac.
- UI checks **passed**: fresh isolated preview opens Sign in; confirmation → Back to create account works; privacy reading enables the required checkbox; close returns to the headset view with Setup/Run locked until an activity is selected.
- Native desktop build **opens Sign in** with its bundled runtime. Offline embedding smoke test and strict signature verification passed.
- Gatekeeper **FAILED**: `Unnotarized Developer ID`. The archive is a signed development artifact, not yet a clean-install participant release. Do not instruct contributors to bypass Gatekeeper as a substitute for fixing distribution.
- Final ordinary-email test did not change mailbox settings, save its password, grant privileges or send a message to Nideesh.

## Current handoff checkpoint — 2026-10-19, results browser update

This checkpoint supersedes earlier notarization and test-count statements above.

- PR #1 head `4c15508` is already an ancestor of the local `codex/contributor-readiness` branch. The new UI work is still uncommitted/unpublished pending Andrew's next release instruction. Preserve the integration checkout; do not overwrite it with the older development tree.
- All 24 automated check groups pass: Python discovery plus 23 JavaScript suites. Seven new local-session tests cover confirmation, active-session refusal, path/link refusal, per-channel acceptance counts and deletion isolation. The older plotting tests now isolate their target functions rather than executing unrelated browser handlers.
- In-app browser checks with disposable synthetic sessions passed: personal and ERP results open directly, Back restores filters, Browse individual sessions restores the list, starring survives return, cancel preserves data, confirmed deletion returns to the browser and removes only the selected fixture. No participant recording was deleted. A physical mouse and real Muse were not retested in this pass.
- Source-only publication audit: 163 files, 483 private strings compared, no unexplained matches or secret/path findings. 107 exact matches were published questionnaire prompts also saved in local questionnaire records; the audit reports these separately. This does not audit arbitrary Git history or the final binary.
- Apple submission `35e64479-3248-42e7-b31f-1e605b9a534d` is **Accepted**, verified directly with notarytool. It covers build 5, not these later edits.
- Status response posted on PR #1: https://github.com/aneff8626/Bandstand/pull/1#issuecomment-6273247491 . No merge, push or release publication was performed.

### Before publishing the final contributor build

1. Finish Andrew's remaining UI edits; rerun the automated suites and source audit against that exact candidate.
2. Inspect and stage only the intended source/test/documentation files, including the new `session_store.py`, `enneagram_items.py` and regression tests. Keep all participant archives, local settings, keys, logs and generated bundles out of Git.
3. Commit/push the integration branch when Andrew says to publish. Resolve PR #1 using its already-integrated ancestry; do not reapply or squash away its fixes accidentally.
4. Package the final source with the stable signing identity, notarize that exact artifact, staple, verify Gatekeeper, and attach a versioned download. Test an install/reopen/update on a separate Mac. Recheck Bluetooth, typing capture and physical mouse Back.
5. Confirm Nideesh's repository invitation/access; prior owner reauthentication blocked the invitation. Fork/PR contribution is already demonstrated, direct write access is not verified.
6. Complete live staging two-account isolation/consent/withdrawal/deletion tests and a production ERP delivery smoke test before claiming that shared ERP service is fully accepted. The 31 local migration checks and prior ordinary production signup test are useful but narrower evidence.

**No scientific or protocol decision is required to share this as a developer preview.** It is not a fully accepted participant release yet. Synthetic personality comparisons remain explicitly labeled. Shared decoder aggregation remains disabled by Andrew's instruction; 20 confirmed non-test users triggers reconsideration, not automatic activation. Local session deletion leaves existing shared ERP copies and external exports intact, which the confirmation states explicitly.

## Published-source checkpoint — October 19, custom feedback

Andrew authorized a source push after final interface checks. This update includes the earlier unpublished results/personality work, PR #1 integration, exclusive session/browser navigation, local deletion confirmation and synthetic comparison plots.

Custom feedback now accepts a continuous 1–40 Hz range, with direct numeric limits and graph dragging. The selected limits are saved; power is integrated over interpolated PSD edges and used for baseline, live feedback and training scores. Fine selector precision does not increase the spectral resolution of the underlying two-second EEG clips. Selected electrodes have green rings; excluded electrodes have dashed neutral rings. Wide screens use a two-column customizer. Combined Results retains a prominent provisional banner and is not presented as a finished group-analysis feature.

Verification: all 24 automated check groups pass, including fractional-edge integration and invalid-range rejection. In the isolated browser, 8.15–12.35 Hz with TP9 excluded started, produced live feedback using the remaining channels, and saved 21 clips with custom-band power. The final dialog and results banner were visually inspected. Hardware, live production ERP delivery, and a newly packaged binary were not verified in this pass. The GitHub push is source code; build 5 notarization does not cover these newer edits.
