# Milestones three and four: shared writing-decoder model (groundwork, disabled)

**Participant contributions remain disabled.** Nothing in the app calls these pieces. No round, model or update
leaves a device. `enrollment.py` still reports `decoder_upload_enabled: false`, and the database still
constrains `decoder_sharing` to false. The handoff's gates — a threat model, chosen parameters, a security
review, new specific consent and a reviewed pilot — are not met. This work makes those decisions concrete and
testable; it does not take them.

## Status

| Deliverable | Implemented | Tested with synthetic data | Cloud / real participants | Security review |
|---|---|---|---|---|
| Common model and objective (Andrew's `local_round_update`: ridge gradient in release-fixed coordinates) | existing + encoder pin + memory budget | yes | no | no |
| Signed release format, verified before loading, rollback (`shared_model.py`) | yes; **no key trusted yet** | yes (5 tests) | no | no |
| Isolated contribution format: delta only, no text, no count (`shared_learning.contribution`) | yes | yes (canaries, determinism, shape, norm) | no | no |
| Bounded training worker that never stalls acquisition (`train_isolated`) | yes | yes | no | n/a |
| Secure aggregation (Flower 1.40 SecAgg+) with dropouts | yes, harness only | yes (F1–F3) | no | **no** |
| Client-side refusal of lying or replayed rounds and of small cohorts | yes, harness only | yes (F4–F6) | no | no |
| Distributed Gaussian noise and an RDP privacy ledger | yes, harness only | yes (F7) | no | no |
| Robustness to a malicious participant | **no**: measured only | F8 observed | no | no |
| Coordinator service, Supabase round tables, consent receipts | no | no | no | no |

## What was built

**Releases (`shared_model.py`).** One file per release: `BSM1`, a JSON header and float32 tensors
(`mean`, `scale`, `weights`), followed by an Ed25519 signature. Loading checks, in order:
- size and signature, against keys built into the app;
- the exact header fields;
- format and model family;
- feature schema;
- the pinned public encoder (`all-MiniLM-L6-v2` at revision `1110a243…`, the same revision the download
  script verifies);
- tensor shapes, hashes and finiteness;
- that metadata is numbers only.

Nothing is unpickled or executed. Installing keeps the previous good release. If the current one stops
verifying, the app falls back to the previous one, and `rollback()` is explicit. `TRUSTED_KEYS` is empty, so
today every release is refused. The project would keep the private key offline.

**Contributions (`shared_learning.py`).** Rounds must name the pinned encoder, because targets come from it.
`contribution()` serializes only the clipped delta, plus round ID, parent hash, shape and hash.

The example count is left out on purpose. Participants are weighted equally, and a count would reveal how much
someone wrote. That is a design decision for Andrew.

`read_contribution()` is the matching check for a plaintext coordinator, used only where secure aggregation
is not.

`train_isolated()` computes a round in a separate low-priority process with a time limit. The parent's 100 Hz
loop never paused for more than 0.25 s while 3,000 examples trained.

Tests plant random canary strings in every text column of a synthetic archive. None appeared in the
contribution bytes, its header, logging, stdout or stderr. Canaries detect accidental copying; they are not
proof against statistical reconstruction from the numbers, which is what secure aggregation and noise are for.

**Synthetic federation (`federation/`, separate environment, not bundled).** `federation/run_synthetic.py`
runs Flower 1.40 SecAgg+ with eight synthetic participants. Each has its own archive (participant-specific
feature shift, shared hidden mapping, canary texts) and runs Andrew's update function.

Each participant:
1. checks the parent hash of the model it received;
2. refuses round IDs it has already answered;
3. refuses an announced cohort below its own floor;
4. refuses a different encoder;
5. checks its own contribution;
6. adds Gaussian noise with standard deviation σ·C/√(min cohort);
7. returns weight 1 through `secaggplus_mod`, which masks the update.

The coordinator's strategy publishes a round only if the privacy ledger allows it. A recording wrapper keeps
every reply the coordinator received, as evidence.

| ID | Scenario | Result |
|---|---|---|
| F0 | Control: same rounds **without** SecAgg | coordinator replies correlate 1.000 with individual updates: the detector works |
| F1 | 3 rounds, 8 participants | aggregate = plaintext mean (max error 2.0e-6); 576 coordinator arrays vs every update: max \|corr\| 0.048; no canary text reached the coordinator; held-out loss 1.000 → 0.107 |
| F2 | 2 drop after key sharing | published with the 6 survivors; aggregate = their mean (2.3e-6) |
| F3 | 3 drop with threshold 6 | no aggregate; nothing published |
| F4 | Coordinator lies about the model | every participant refused; nothing published |
| F5 | Round ID reused | second round refused by all |
| F6 | Announced cohort 2 below floor 5 | all refused |
| F7 | σ = 1, illustrative budget | ε after 1/2/3 releases 5.22/7.77/9.85 (δ = 1e-6); releases 3–4 refused; noise in the mean 0.0773 vs 0.0791 expected |
| F8 | One participant sends 1000 per coordinate | **observed**: SecAgg+ clips to ±8 per coordinate, but the mean still moves by up to 1.0 per coordinate (L2 58.8) against honest norms ≤ 0.5 |

Full matrix: `docs/acceptance/federation-synthetic-20261017.md`. Rerun:

```sh
uv venv --python 3.12 .venv-fed && uv pip install --python .venv-fed/bin/python -r federation/requirements.txt
.venv-fed/bin/python -m federation.run_synthetic
```

## Threat model (draft for review)

| Adversary | Defence here | Residual risk |
|---|---|---|
| Curious coordinator | SecAgg+ masking; distributed noise, so the aggregate itself is noised | Learns the noised average and who took part (identities, timing, IP) |
| Lying coordinator (different model to different people, replayed rounds, tiny cohort) | Parent-hash, replay and cohort-floor checks on each device | Can still simulate fake participants (Sybils) to isolate one person. Needs authenticated cohort membership, e.g. Supabase-issued round tokens counted by an independent party |
| Colluding participants | SecAgg+ threshold; noise share sized for `min_cohort` honest contributors | If fewer than `min_cohort` honest people take part, noise falls below the accounted level |
| Malicious participant (poisoning) | Per-coordinate clipping inside SecAgg+ only | **Unbounded in effect relative to honest updates (F8).** Needs per-client norm proofs, a much lower clipping range, robust aggregation, or a trusted-enclave design. Not solved |
| Network observer | TLS in a real deployment (not in the simulation) | Metadata |
| Compromised participant device | None | Local archive, embeddings and checkpoints are exposed, as today |
| Released model | DP noise and ledger; signed releases | ε as chosen; quantization in SecAgg breaks exact Gaussian guarantees (a discrete Gaussian mechanism would be needed) |

## Decisions required before any real round

Each of these is Andrew's or a reviewer's call. The harness values (8 participants, threshold 5,
`min_cohort` 5, C = 0.5, σ = 1, ε ≈ 8.8 at δ = 1e-6) only exercise the code; they are not recommendations.

- **Cohort and dropout:** minimum cohort, reconstruction threshold, client floor, dropout tolerance and timeouts.
- **Contribution limits:** clipping norm, SecAgg+ clipping range (match it to the norm), learning rate,
  rounds per release, one contribution per person per round, repeat-participation limits.
- **Privacy:** noise multiplier, privacy unit (participant-level), ε/δ budget, release frequency, and whether
  the coordinator is trusted with the unnoised aggregate. Here it is not, hence distributed noise.
- **Weighting:** equal per participant (as built) or capped by example count.
- **Robustness:** a strategy against malicious clients (F8).
- **Withdrawal and unlearning:** influence already in a released model cannot be removed. This must be
  disclosed before consent; decide whether to retrain.
- **Evaluation:** cross-participant held-out evaluation against no-EEG and text-history baselines, separate
  from the existing within-user evaluation, before any model is shown to participants. Not built.
- **Operations:** where the coordinator runs, given Flower's SuperLink and the measured memory and duration;
  the Supabase tables and APIs for rounds, authorizations, the ledger and releases (handoff section 8, not
  built); logging limits.
- **Consent:** new, specific consent text for writing-decoder contribution. The current "interest only"
  choice authorizes nothing.

## Not done

Milestone five (a reviewed pilot) is not started; it needs everything above. The Flower deployment engine
(SuperLink and SuperNodes over TLS) is not exercised, only its in-process simulation. Restarting a worker
mid-round is not tested. The semantic encoder and real writing archives were not used; the synthetic
features and targets stand in for them.
