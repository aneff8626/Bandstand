# P300 speller testing

Open **Activity → BCI → P300 speller → Setup → Start activity** with EEG streaming. This is a local experimental prototype, not a validated communication aid.

1. Attend to the cued letter and count its flashes. Eight calibration letters take roughly three minutes. Blink during the three-second gaps.
2. Review whole-letter held-out calibration accuracy (chance: 1/36). Missing predictions count as incorrect. This small, within-session estimate is not expected accuracy for another session or person.
3. Attend to any letter and press **Select a letter**. Five passes through the 12 row/column flashes take roughly 20 seconds. The decoded character appears above the matrix. Space is the bottom-right cell; Delete last letter corrects output manually. Up to eight spelling selections fit in one recording.
4. End & save or Escape. EEG, event timestamps, calibration model, decoded characters and edits are local. Saved Results show calibration ERPs and the final output. P300 spelling is excluded from automatic ERP uploads.

## Implementation

A 6×6 matrix flashes rows/columns for 120 ms at approximately 300 ms onset intervals. Order is shuffled on each repetition. Software timestamps share the engine clock; screen/BLE latency is not physically measured. Hidden display, interrupted timing and stale EEG stop the task. Reconnect and recalibrate after interruption.

The existing causal 0.1–30 Hz plus 60 Hz notch pipeline yields −200…800 ms epochs with prestimulus baseline correction. Each channel is artifact-screened independently. Twelve 50-ms means from 100–700 ms feed separate shrinkage linear discriminants (30% spherical covariance). Each fold fits normalization and classifier on seven letters and predicts the eighth. Final models train on all calibration letters. Available channel discriminants are averaged per flash, then averaged per row/column; maxima identify the character. Every row/column needs at least three usable flashes. No questionnaire, typing, expected spelling target or language model informs predictions.

The live side pane shows per-channel calibration averages with approximate pointwise 95% normal intervals (correlated overlapping epochs limit inferential interpretation). There is no calibrated probability. Spelling flashes are excluded from labeled ERP comparisons. Models are recalibrated each session; no cross-user training is enabled.

This adapts row/column P300 spelling, not a published Muse validation. Conventional successful montages commonly include central/parietal/posterior electrodes absent from Muse. Reference: [Krusienski et al., 2006](https://pubmed.ncbi.nlm.nih.gov/16792299/). Physical timing, real Muse accuracy, fatigue and gaze effects require testing. Avoid the flashing task if flashing is uncomfortable or contraindicated for you.

## Checks

Unit tests cover leave-one-letter-out decoding, missing-channel fallback, target-label independence during spelling, missing-row abstention and insufficient training. Browser testing exercises calibration, local save and stop. Synthetic tests establish plumbing only, never real EEG performance.
