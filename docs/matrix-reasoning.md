# Matrix reasoning

Bandstand uses MaRs-IB short form 1: three practice puzzles and 12 scored puzzles, each with a 30-second deadline. Original images and published parameters come from [Zorowitz et al. (2023)](https://doi.org/10.3758/s13428-023-02067-8) and the [authors’ implementation](https://github.com/ndawlab/mars-irt). Stimuli were extracted unchanged from its validation-A image archive. The manifest records their SHA256 hashes.

## Interpretation

The test estimate is a reasoning score on a 100/15 scale relative to the published online US adult research calibration. It is **not a representative population IQ norm, age-adjusted IQ, or full-scale IQ measurement**. It should not be used for educational placement, clinical decisions, or employment decisions. Children and other populations require separate validation. Repeat exposure can change performance.

For each item, p(correct | theta) = gamma + (1 − gamma) × logistic(alpha × theta − beta). The posterior multiplies these likelihoods by a standard-normal prior, evaluated on 2,001 points from −5 to 5. The displayed score is 100 + 15 × posterior mean theta. Whiskers are the 2.5th and 97.5th posterior percentiles transformed to that scale. They assume fixed published parameters; they exclude uncertainty about transferring the calibration to Bandstand users. Early estimates depend strongly on the prior. Incorrect and timed-out items count as incorrect; unanswered items are omitted.

Practice repeats until correct and is excluded from scoring. Choice order is randomized; item order follows the published form. The server enforces deadlines and rejects stale item tokens. Real-time score feedback is an adaptation of the validation procedure and may influence subsequent responses. The panel can be hidden during the test. This adaptation itself requires validation.

## EEG comparison

The adjacent EEG display is explicitly a **synthetic demo with no demonstrated IQ accuracy**. A fixed arbitrary band-power transformation drives it; questionnaire responses never enter that transformation. No confidence interval is assigned. It must not be described as a validated prediction or interpreted as evidence of intelligence. Developing an actual predictor requires consented paired recordings, independent participants held out from training, comparison with a non-EEG baseline, and externally validated calibration.

Responses, timing, item version, continuous EEG, per-channel usable clips, spectral summaries and both displayed scores remain in the local personal-session store. This activity adds no upload route and does not enable shared decoder contributions. Existing local deletion controls apply. Test sessions using simulated EEG remain labeled simulated in the session browser and results.

## Licensing

Bandstand code remains MIT. The MaRs-IB stimulus images embedded in `web/matrix-assets.js` are **CC BY-NC 3.0**, attributed to the MaRs-IB creators (Chierchia et al., 2019); commercial reuse requires separate permission or replacement stimuli. See `matrix-stimulus-license.md`. Published parameter/implementation material is MIT, copyright Daw Lab; see `matrix-parameter-license.md`. These notices are included in desktop builds. This module is not an official Raven’s test and contains no proprietary Raven’s items.

## Mixed pilot protocol update

New sessions now include three original pilot items (15 test puzzles total), randomly interspersed without changing reference-item order. They do not contribute to scoring. Results display reference percentiles and their transformed credible intervals rather than 100/15 scores. See [the pilot-bank methods and calibration plan](matrix-original-bank.md). The mixed administration and live feedback need validation; no model is automatically trained or activated.
