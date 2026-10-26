# Spectral demo statistics

These are exploratory comparisons of the recorded periods within one person, conditional on those periods. They are not population or causal tests. Condition, time, contact and order can remain confounded.

Descriptive band power uses non-overlapping clean 2-second log-power segments, including partially usable and currently running blocks. Mean appears at one segment; sample SD at two. Condition plots show segment observations and mean ± SD. Each block view preserves condition colors, block order and a marker for the in-progress block; spectra can also be inspected individually.

Inference uses 999 deterministic moving-block bootstrap draws, separately within each continuous run; chunks never span artifact gaps or experimental blocks. The mean weights each clean segment equally. Bootstrap mean errors are centered to reduce moving-window edge bias. Chunk length starts near the cube root of segment count, limited by continuous run length, and increases using within-run autocorrelation. A conservative t-based small-effective-sample inflation is applied. The approximate basic 95% interval and two-sided centered-bootstrap p-value are for condition A minus B. This is a provisional heuristic estimator, not a proven calibration guarantee.

Availability requires at least 12 segments (24 clean seconds) per condition, at least four chunk lengths of data (eight for strong lag-one dependence), and runs longer than the chosen chunk. Flat data, insufficient resampling variation and large within-run linear drift suppress inferential output while retaining descriptive statistics. Highly fragmented recordings may need substantially more data. This replaces the ten-completed-block requirement for selected-band tests, not the existing across-block PSD shading rule.

For more than two conditions, pairwise comparisons use Holm correction across all condition pairs within each electrode. Neither correction across electrodes/band searches nor sequential correction across live looks is applied. Do not interpret a transient p<.05 as a stopping rule. Rejection-related missingness and dependence beyond the resampled chunks remain limitations.

Live analysis includes completed 2-second segments from the pending block and updates as they accumulate. No partial preview is persisted as an extra trial. Old recordings are reanalyzed using their saved spectral windows. PDF reports identify the new method.

Validation includes deterministic shift/null tests, artifact-gap/short-data/drift/flatline guards, multi-condition correction, and seeded autocorrelated simulations. Simulations are engineering checks, not validation on Muse users. Strongly correlated short recordings often have no inferential output.
