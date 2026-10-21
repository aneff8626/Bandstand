# Experimental P300 speller

The 6 × 6 matrix uses eight cued calibration letters, then uncued spelling selections. Each selection presents five repetitions of all six rows and all six columns. A row or column needs at least three usable flashes; rejection is per electrode.

## Try it

Open **Activity → BCI → P300 speller → Setup → Start activity** with EEG streaming. Count flashes of each cued letter for about three minutes. After calibration, attend to any letter and press **Select a letter**, then **Add next letter** for subsequent selections. Each takes about 20 seconds. Space is the bottom-right cell. **Delete last letter** corrects output; **End & save** or Escape saves locally. Up to eight spelling selections fit in one recording. P300 spelling is excluded from automatic ERP uploads.

Flashes last 120 ms with approximately 300 ms onset intervals. Hidden display, interrupted timing or stale EEG stops the task. The analysis uses causal 0.1–30 Hz filtering and a 60 Hz notch, −200…800 ms epochs and prestimulus baseline correction. No typing, language model or intended spelling target enters predictions. Conventional successful montages often include central/parietal/posterior sites absent from Muse. See [Krusienski et al., 2006](https://pubmed.ncbi.nlm.nih.gov/16792299/). Stop if flashing is uncomfortable.

## Electrode-specific timing

For each usable electrode, calibration searches intervals of 100–400 ms duration, in 50 ms increments, within 100–800 ms after the flash. Inner whole-letter validation chooses the interval by mean within-letter target/non-target AUC. In exact ties it prefers a broader interval. These are bounded engineering search choices, not a claim that one interval is physiologically optimal. Channels without at least three viable inner folds are omitted.

The classifier uses 50 ms features within that interval and a shrinkage covariance estimate. Electrode scores are averaged for each flash using only accepted channels. Every outer held-out-letter validation fold repeats the entire inner window search and classifier fitting on the other seven calibration letters. The outer letter never influences selection. Final training uses all eight letters. Overall and per-electrode percent correctly decoded letters count unavailable predictions as incorrect; chance is 1/36. A flash classifier that always says “other” would score 83.3%, so plain flash accuracy is deliberately not the headline.

Results shade each electrode’s own interval and calculate its mean amplitudes using that same interval. Dragging a plot changes only that electrode’s descriptive comparison, not the trained decoder. Ordinary t-test significance is suppressed for calibration-selected intervals. Older recordings are reanalysed in memory, clearly marked, preserving their original decoder accuracy and files. The full source recordings are not overwritten.

Temporal/channel feature selection has precedent in [spatio-temporal P300 feature-selection research](https://pmc.ncbi.nlm.nih.gov/articles/PMC3193982/). This implementation is a simpler supervised method, not a reproduction or evidence of validated Muse performance. Repeated-flash dependencies, eight-letter calibration size, overlapping ERP epochs and software-only timestamps limit interpretation. More calibration or a different feature representation may outperform the selected interval.

## Output and evidence

The backend owns accumulated text and a per-letter history in local session metadata. Prediction requests are idempotent by selection group. Deletion removes the last character and its displayed evidence; the original acquisition events remain in the recording. Retrying an earlier prediction does not restore a deleted letter. Results show the saved text and history, including recordings from earlier app versions when those fields exist. A calibration-only recording has no spelled word.

Each letter includes the winning row and column score gaps relative to their runners-up. These are standardized classifier evidence units, **not probabilities or confidence percentages**. Held-out calibration correct/total is displayed separately. Do not translate either into a claimed individual-letter confidence without substantially more independent calibration/evaluation data.

## UI and checks

Run is an inline workspace. Changed calibration instructions and the cued cell pulse briefly before flashes begin; animation stops during acquisition and respects reduced-motion settings. End & save returns to Results. Returning to Run starts a new speller calibration, never the generic oddball task. Spelling text persists within a session; starting a new session starts a new word.

Regression tests cover distinct electrode windows, refitting within held-out folds, insufficient data, per-channel rejection, absent target labels during spelling, accumulated text, retry/delete behavior and Results → Run routing. Simulated UI checks establish software behavior, not biological decoding performance.

## Interpretation limits

“Cued-letter flashes” means a flashed row/column contains the instructed character; attention is not measured by this label. A difference can reflect gaze, automatic visual responses, overlapping responses to later flashes, sequence/refractory effects, unequal artifact rejection or finite-sample noise. At approximately 300–320 ms between flashes, a 600–800 ms epoch contains responses to subsequent stimuli. Frontal measurements are AF7−FPz and AF8−FPz, so the reference can change waveform polarity and apparent peak timing. A negative peak alone does not identify an N400 or a P300. See [gaze study](https://pmc.ncbi.nlm.nih.gov/articles/PMC2992970/) and [stimulus-timing study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3595069/).
