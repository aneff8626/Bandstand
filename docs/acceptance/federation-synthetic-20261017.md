# Synthetic federation run 20261017-162912

Flower SecAgg+ with 8 synthetic participants. Synthetic data only.

| ID | Scenario | Outcome | Evidence |
|---|---|---|---|
| F0 | F0_detector_control | pass | without secure aggregation the coordinator receives each update: max |corr| 1.000 over 64 comparisons, so the F1 detector can see a leak |
| F1 | F1_rounds | pass | published rounds [1, 2, 3]; max |aggregate − plaintext mean| 2.0e-06 (updates up to 0.028); coordinator arrays compared 576, max |corr| with any one update 0.048; canary text seen by coordinator: False; held-out loss 1.000 → 0.107 |
| F2 | F2_dropout | pass | 2 of 8 dropped after key sharing (4 failed protocol messages); published with 6 participants; aggregate equals the survivors' mean (max error 2.3e-06) |
| F3 | F3_below_threshold | pass | 5 survivors below threshold 6: no aggregate, nothing published  |
| F4 | F4_lying_coordinator | pass | every participant refused a manifest whose parent hash did not match the model it received; nothing published |
| F5 | F5_replay | pass | round 1 published; the reused round id in round 2 was refused by every participant (published [1]) |
| F6 | F6_cohort_below_floor | pass | announced cohort 2 is below the participants' floor of 5: all refused; nothing published |
| F7 | F7_privacy_budget | pass | budget ε=8.81 (δ=1e-06, illustrative): published [1, 2], refused [3, 4]; ε after 1/2/3 releases at σ=1: 5.22/7.77/9.85; noise in the mean 0.0773 vs expected 0.0791 |
| F8 | F8_poisoning | observed | one participant sent 1000 per coordinate; SecAgg+ clipped it to ±8.0 per coordinate, still moving the mean by up to 1.00 per coordinate (L2 58.8) against an honest update norm ≤ 0.5. Masking hides individual updates, so the coordinator cannot inspect or reject this; bounded robustness needs a reviewed design (e.g. lower per-coordinate range plus norm proofs or robust aggregation). |
