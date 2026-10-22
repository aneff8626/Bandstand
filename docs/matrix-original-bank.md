# Original matrix pilot bank

## Current implementation

`matrix_original.py` defines and draws 12 original, monochrome puzzles under Bandstand's MIT license. It contains no imported stimulus images, traced MaRs-IB graphics, or proprietary Raven's items. Four rule families (combination, intersection, symmetric difference, and count/rotation) have three variants each. These are **candidate items**, not a validated commercial intelligence test. Human review should assess ambiguity, visual accessibility, language demands, difficulty and distractor quality. Similar rule families do not guarantee equivalent difficulty.

A session contains the existing three practice items and 12 MaRs-IB reference items, plus three pilot items. The server selects three distinct families, draws one variant per family, and inserts them into distinct randomly chosen internal gaps. Reference-item order is preserved. Choice positions are independently randomized. Sibling variants do not appear together. Each item has a 30-second limit. Existing saved sessions without a mixed-item plan retain their original 12-item administration.

Pilot answers never affect the reference score. Item ID, bank version, rendered-stimulus SHA256, canonical response, correct/incorrect, timeout, presentation position, option order, onset and response time are retained locally alongside reference responses and EEG. This is collection infrastructure, **not automatic training or central aggregation**. This feature adds no upload endpoint or sharing consent. A local aggregate inventory is available through `python scripts/report_matrix_pilots.py /explicit/personal-session-directory`; it excludes simulations and incomplete reference tests and prints no personal identifiers.

## Percentile display

The displayed percentile is 100 × Phi(theta estimate), where Phi is the standard-normal CDF assumed for the published reference ability scale. The 95% posterior endpoints are transformed through Phi separately. It is not percent correct. The bell curve depicts that model, not an empirical population distribution or a histogram of app users. Old saved 100/15-scale scores convert back to theta for display. EEG's gold marker remains a synthetic, unvalidated illustration.

Interspersal, timing changes and real-time feedback can affect performance. Thus even reference-item results in the mixed protocol need comparability testing; the original validation does not establish norms for this administration. Hiding the live panel is available. Full-scale IQ and age-adjusted population percentiles are not claimed.

## Calibration and replacement procedure

1. Review every puzzle and distractor independently; revise ambiguous items with new immutable IDs/versions. Keep excluded items and versions identifiable. Never overwrite an item while retaining its ID.
2. Collect consented data from varied participants, with enough coverage per item across the reference ability range. Track repeat exposure and use pseudonymous participant identifiers for deduplication. Session counts are not participant counts. Establish sample size using simulation of parameter precision and desired validation accuracy; there is no universal small number that makes these items calibrated.
3. Randomly assign participants to reference-only versus mixed administration to estimate the effects of insertion and live feedback. Freeze these procedures for the validation sample.
4. Fit candidate item response curves using reference-item response likelihoods to anchor ability, propagating uncertainty in ability rather than treating point estimates as error-free labels. Compare 2PL and constrained-guessing 3PL models, inspect difficulty, discrimination, distractor performance, timing, missingness, local dependence and differential item functioning. Separate variant siblings across training/validation to check family overfitting.
5. Hold out entire participants for validation, including repeat sessions. Assess measurement precision, calibration, stability, convergent validity and subgroup performance. A fit on the collection sample is not validation. EEG modeling requires an independent evaluation against a non-EEG baseline; survey-derived labels must not leak into the EEG predictor.
6. Publish a versioned reviewed parameter bundle and clear limits; activate it only after review. Retain older scoring versions for reproducibility. Replace all MaRs-IB test AND practice assets before distributing a commercial build without separate permission. A commercial percentile claim also needs a defined and suitable reference population; accurate linking alone does not establish population norms.

## License boundary

The original pilot code/artwork is offered under MIT. The mixed app still includes CC BY-NC 3.0 MaRs-IB stimuli; adding original material does not remove that restriction. Commercial distribution requires removing or licensing those assets and reviewing the intended use of the reference materials. Do not treat this development exercise as a blanket clearance of all third-party rights.

Sources: [MaRs-IB IRT validation](https://doi.org/10.3758/s13428-023-02067-8), [IRT overview](https://arxiv.org/abs/2108.08604), [anchor-item invariance](https://pubmed.ncbi.nlm.nih.gov/22468848/), [Creative Commons noncommercial interpretation](https://wiki.creativecommons.org/wiki/NonCommercial_interpretation).
