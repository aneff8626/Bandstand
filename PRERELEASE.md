# Bandstand 0.3.0-alpha.1 — extremely early development preview

Source-code prerelease for contributor review. Not a stable or validated participant release. No new macOS app binary is included; the previous binary does not contain these changes.

## Changes
- Headset-first workflow, grouped Setup/Run steps, category tabs and book-to-wave branding.
- Live power spectrum, band visibility/grouping, stable axes and motion display smoothing.
- Simpler task setup and participant forms; right-side questionnaire inference display with automatic answer advancement.
- 100 explicitly synthetic demo subjects, with 200 Big Five/Enneagram records isolated from real participant data and uploads.
- Local cumulative decoder groundwork and exploratory growth activities.

## Limitations
- Personality estimates are synthetic nearest-neighbor demonstrations, not validated EEG personality inference. Synthetic personality labels and EEG were generated independently. The nine-item Enneagram questionnaire is unvalidated.
- Protected cross-user writing-decoder training/upload is not implemented. Raw writing, embeddings and personal checkpoints remain local.
- Artifact-training controls are intentionally disabled.
- Full visual, headset, account/email, clean-machine and sustained recording acceptance remain outstanding. Expect UI bugs and breaking changes.

## Checks
- 113 Python tests passed; JavaScript regression checks passed after updating the display-filter test for separate high/low-pass controls.
- Isolated simulated browser startup passed after the setup-layout crash fix.
- Source publication audit passed: explicit allowlist, secret/path scan and 376 private-string comparisons. No recordings, credentials or personal models included.
