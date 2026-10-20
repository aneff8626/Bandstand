# Experiment review (v0.3.0-alpha.1)

This review answers Dr. Neff's two requests:

1. Each experiment should be functional, with no placeholders.
2. Each experiment should get suggested improvements to the UI, the methods, and how results are shown.

**How it was tested.** Four parallel audits ran every activity end to end in isolated copies of the
browser preview, using synthetic EEG. Faces and expertise used generated test drawings, and writing used
a synthetic stand-in for the headset. The audits ran every export and read the code.

**What the fixes are and where.** The fixes are on branch `experiments`, which sits on top of `backend`
and `app-edits`. Each one was re-checked in the real screens; the scripts are in `build/ui/`.

**What was not tested.** Nothing here was run with a real Muse, real stimulus timing, or the native app
shell. Each of those is noted where it matters.

Status key: **Fixed** = changed and re-verified on this branch. **Suggested** = recommendation, not
changed. **Decision** = needs Dr. Neff's call.

## Verification of the fixes (local preview, synthetic EEG, 2026-10-17)

The full record is `docs/acceptance/experiments-local-20261017.md`.

- **Simulated effects now point the textbook way.** Each task was run long enough for statistics. With
  t = (condition 1 − condition 2) / SE:

  | Task | Result |
  |---|---|
  | Oddball, TP9/TP10 | t = −13.2 / −13.0 |
  | Faces, TP9/TP10 | t = −4.1 / −5.3 |
  | Flanker, AF7/AF8 | t = +2.5 / +2.7 |
  | Reward, AF7/AF8 | t = −11.3 / −8.2 |
  | Eyes open/closed (with block-to-block variability), all four channels | t = −4.4 to −8.4 |
  | Arithmetic, AF7/AF8 | t = −14.9 / −14.3 |
  | Biofeedback (nothing injected) | t ≈ 0, p > .4 in three runs |

- **Writing lag** was measured for 7 minutes on both builds with a synthetic live bridge, the same script
  and the same machine. The unfixed build kept the EEG lag near 0.03 s until about 850 words, then rose to
  0.36 → 0.55 → 0.72 s and was still rising; the audit saw it reach 2.85 s and stop. The fixed build stayed
  at 0.03–0.06 s (one 0.21 s peak) over 940 words.
- **Re-verified checks:** image import from Setup; audio gain refused for 3, empty and 0 in the page and
  for 3 in the engine; no tallies in counting tasks; both hidden experiments offered; behaviour tables for
  flanker, reward and biofeedback; reward plan without pre-drawn outcomes; restart after Escape in under
  4 s; local "No" save; biofeedback 6 + 6 blocks with a working comparison.
- **Found and fixed while verifying:**
  - Results were cached by trial count only, so behaviour that arrived after the last trial (the
    biofeedback posttest, late responses) did not appear. The cache now also keys on events.
  - Once biofeedback could reach its minimum, the pooled ERP plot crashed on a missing confidence band
    (fewer than 10 trials), which stopped the rest of the results from redrawing.
- **Tests:** 158 Python tests pass (new: image decks, behaviour summaries, report builds); all JavaScript
  regression scripts pass; the release audit passes.

## App-wide

| Item | Status |
|---|---|
| Audio gain accepted any value: 3 played 75× the default, and an empty field ran silently while recording | **Fixed**: 0 < gain ≤ 0.2 is enforced in the page and the engine, the tone is capped, there is a test tone, and the eyes-open/closed cues follow the setting |
| Synthetic EEG taught wrong results. TP10 showed reversed eyes-closed alpha; reward could never show an effect; flanker N2 had the wrong sign; faces had no N170; biofeedback showed a fake +84% training effect | **Fixed**: effects now depend on the protocol and channel. Nothing is injected for biofeedback or disclosure. The simulation banner states what was injected. Background alpha drifts and each block's effect size varies, so the statistics are not unrealistically clean |
| Participant screen showed running per-condition counts, giving away the answer in the counting tasks | **Fixed** for oddball, auditory and reward; counts also hide whenever the EEG panel is collapsed |
| Live EEG panel open by default on the participant screen | **Decision**: kept, as designed for classroom display. Suggested: a "participant view" default for research runs |
| PDF report: "MUSE LAB" branding, raw Python lists, p printed to 8–12 digits, TF processing text on ERP reports, unlabelled ERP plot, trial numbering different from the CSV | **Fixed** |
| Results show no trials-completed or end-reason summary | **Fixed** in the PDF ("N of M planned", state); **Suggested** on screen |
| "Time: about 1 minutes" | **Fixed** |
| README contradicted the code: eyes open/closed timing, TF windows, biofeedback rest; it said personal activities keep no raw EEG, but they do | **Fixed** |
| Contribute to research could not save "No, keep my data local" without an account, and stayed highlighted forever | **Fixed**: local-only choices save on this computer; "Yes" for ERP still asks you to sign in |
| Two "Contribute to research" controls (cloud sharing vs a local "research interest" checkbox that does nothing) | **Suggested**: merge them |
| No visible demo ↔ live switch (`#previewSource` hidden; leaving demo needs `/?live=1`) | **Suggested** |
| "Expected results" dialog repeats the notes and never states an expected effect | **Suggested**: protocol-specific direction, window, rough size and trials needed |
| Validation (trial count, categories, images) happens only after preflight | **Suggested**: validate in Setup |

## Visual oddball (P300)

Works end to end, including the full 120-trial run, Escape, rejection, recomputing the analysis window,
saved sessions and every export.

- **Fixed:** the participant tally is hidden. The synthetic P300 is larger for targets at TP9/TP10
  (t ≈ −13 in a 60-trial check).
- **Suggested (UI):** ask "How many blue circles?" at the end as an attention check.
- **Suggested (methods):**
  - Pure green is about 10× brighter than pure blue, so target and luminance are confounded. Offer
    counterbalanced or equal-brightness colours.
  - 120 trials gives only 30 targets. Recommend 240, and warn live when targets fall below the minimum.
  - Offer zero-phase offline filtering for results; the causal 30 Hz low-pass delays peaks by about 7–8 ms.
- **Suggested (results):**
  - The pooled TP9+TP10 result appears only in the PDF; show it on screen first, then per channel.
  - Add a target − standard difference wave with CI.
  - Report the mean difference, 95% CI and Cohen's d, with the direction stated.
  - Show accepted/total against the minimum.

## Faces & cars (N170) and Objects of expertise (N170/N250)

- **Fixed (blocker):** the Stimulus library was unreachable after the redesign. Setup now shows image
  counts against the minimum of 20 and an "Import or review images" button.
- **Fixed (method):** images repeated back to back and were used unevenly (about 40 immediate repeats in
  160 trials, which confounds N170 repetition suppression). Each condition now cycles through a shuffled
  deck with no immediate repeats; tested over 800 random sessions.
- **Fixed:** the experienced/unfamiliar roles are kept in the labels, e.g. "Experienced: birds"; faces
  shows "Faces/Cars". The expertise pickers are centred in Setup. The synthetic N170 is larger for faces
  (t = −4.1 / −5.3).
- **Suggested (UI):** thumbnails, delete, per-image provenance; a "needs image set" badge on the cards
  (`ready=False` is never read); a 1–7 knowledge rating for each expertise category, stored with the
  session.
- **Suggested (methods):**
  - Normalise within the object area, not the grey padding (`server.py:115-119`).
  - Add an attention task (1-back or catch trials).
  - Optionally add scrambled controls.
  - Recommend ≥ 40 images per category.
  - Counterbalance or redesign expertise roles, since the categories differ in more than expertise.
  - State plainly that N170 sites (P7/P8) are absent on Muse.
- **Suggested (results):** a difference wave; peak latency next to amplitude; the image used on each
  trial and its manifest in the exports and PDF.
- Note: CSS cannot change the synthetic drawings used for testing; real photographs were not used.

## Auditory oddball

Works end to end, including 160 trials and tone frequency matching the condition on every trial.

- **Fixed:** gain safety; the participant tally is hidden; the synthetic N1 and P300 are now present.
- **Suggested (methods):**
  - Re-reference AF7/AF8 to the TP9/TP10 mean, as reward does, or use the TP9/TP10 montage.
  - Add an N1 window (about 80–150 ms) to match "N1 / P300" on the card.
  - Require ≥ 2 standards between targets and start with standards (the audit saw 8 back-to-back pairs).
  - Export the audio latency used for each event.
  - Note that equal digital gain is not equal loudness.
  - Suggest 240–300 trials.
- **Suggested (results):** difference wave; N1 and P3 values; accuracy of the participant's count.

## Flanker (N2)

Works end to end. The audit recorded responses correctly: wrong keys, ignored keys, double presses and misses.

- **Fixed:** accuracy and RT were recorded but shown nowhere, although the README promised them. They now
  appear in the results "Task behaviour" table (accuracy, errors, misses, median correct RT, congruency
  effect), the PDF, and `trial-summary.csv` (`response`, `correct`, `rt_ms`). The synthetic frontal N2 is
  more negative for incongruent trials.
- **Fixed:** Escape during a response no longer blocks a restart; the pending key wait is cancelled.
- **Suggested (methods):**
  - Use fixed-SOA timing (currently 1.7–2.8 s, depending on the response).
  - Take RT from `KeyboardEvent.timeStamp`, and stimulus onset after paint.
  - Log late and extra key presses.
  - Option to exclude error trials from the N2.
  - Balance direction × congruency.
  - Correct the citation: ERP CORE's flanker targets the LRP/ERN.
- **Suggested (UI):** fuller instructions and a 10-trial practice block.

## Reward feedback (reward positivity)

Works end to end. Choice mapping and win probabilities (.60 blue / .10 green) are correct.

- **Fixed:**
  - Draws are seeded from the session seed, so they are reproducible and match the listed seed.
  - A "choice shown" time was added, so choice RT is now logged, with p(win) and the outcome.
  - The stored plan no longer contains pre-drawn win/loss labels; 47 of 100 used to contradict the outcomes.
  - The instruction changes to "Feedback" during feedback.
  - Headings say "feedback-locked".
  - The "Choice behaviour" table shows choices, skips, win rate and median choice time, also in the PDF.
  - The synthetic effect survives the TP9/TP10 re-reference (t = −11.3 / −8.2).
- **Suggested:**
  - Draw the squares with CSS colours, not emoji (emoji colour depends on the font).
  - Highlight the chosen square.
  - Matched-shape feedback ('$' and '0' differ physically).
  - A learning curve (proportion blue over trials).
  - A win − loss difference wave.

## Eyes open & closed (alpha)

Works end to end. Statistics use n = 10 blocks per condition, as documented.

- **Fixed:** the synthetic effect is now more alpha with eyes closed on every channel (it was reversed at
  TP10); cue volume follows the gain setting.
- **Suggested (methods):**
  - With exactly 10 blocks per condition, one rejected block disables the test. Default to 30–40 blocks or
    allow a minimum of 6–8.
  - Use a paired or cycle-level test, or a permutation test that respects block order, instead of an
    unpaired Welch test on autocorrelated blocks.
  - Report dB difference with CI.
- **Suggested (results):**
  - One large dot per block, with clips faint.
  - An alpha time course across blocks.
  - A closed − open difference spectrum.
  - A shared colour scale with a colour bar on the TF maps.
- The y axis no longer forces 0 for dB, p is formatted, and the axis is labelled "Condition" rather
  than "Stimulus category".

## Rest & mental arithmetic (theta)

Works end to end. A null result was correct for the old simulator, which injected no theta.

- **Fixed:** a Theta 4–7 Hz band preset; a synthetic frontal theta increase during arithmetic.
- **Suggested:**
  - Collect a final-answer response per arithmetic block.
  - Use restricted randomisation; the shuffled order allowed runs like `00001111`.
  - An ocular/EMG check per block, since AF7/AF8 theta is easily contaminated.
  - Say plainly that this contrast is often null on Muse.
  - Show alpha alongside theta.

## Your own conditions

- **Fixed:** it was filtered out of the activity list (`p.id!=='custom'`) and is offered again. **Decision:**
  if it was hidden on purpose, restoring the filter is one line in `web/app.js`.
- **Suggested:** per-condition instructions and optional cues; configurable block length and gap (8 s
  random switching is unrealistic for "Meditation / Lecture questions"); wire up the half-built
  `customParadigmName`.

## Public self-disclosure

Works end to end. Answer text is not saved anywhere.

- **Fixed:** with quick answers the question pools ran out mid-block, and the remaining "rest" was counted
  as the condition; questions now cycle. An empty Enter is logged as a skip, not as an answer. The PDF no
  longer says "one observation per block" for this task.
- **Decision:** the question "The very worst part of this class — for the love of God, what must change?"
  is not a personal-disclosure item.
- **Suggested:**
  - Four 30 s blocks cannot support block-level inference: use 8–12 shorter blocks or report descriptively.
  - Report typing and EMG confounds per condition (characters, keystroke rate, high-frequency power).
  - Count only clips from accepted blocks (`tf_analysis.py:33`).

## Alpha training & behavior (biofeedback)

- **Fixed (blocker):** it was hidden from the activity list and is offered again (**Decision** as for
  custom).
- **Fixed:** it analysed the wrong data. Blocks were 8 s, but the engine assumed 12 s, so each block
  included 4 s of the next phase. The engine now uses the duration each block reports, and the protocol
  states 8 s blocks.
- **Fixed:** the statistics could never run (3 blocks against a minimum of 10). Pre and post are now six
  8 s blocks each, with a minimum of 5.
- **Fixed:** results showed an ERP-style "Block-locked filtered EEG" plot on a millisecond axis; it is
  hidden for biofeedback. Math accuracy and RT before and after now appear on screen ("Math performance"),
  not only in the PDF. The "Training · 1 s remaining" label no longer sticks.
- **Suggested:**
  - Use log power for features and feedback.
  - Smooth the feedback (EMA) with a shaping target.
  - Use TP9/TP10 for blink rejection.
  - Add a sham or no-feedback control; without one, pre/post reflects time and fatigue.
  - Use more than 5 math items.
  - Show a training curve with artifact gaps shaded.

## Personal activities

**Works:**
- Big Five (IPIP keying and scoring verified).
- Enneagram.
- Meditation.
- Find your reset.
- The personality demo, labelled synthetic everywhere.
- Participant forms.

**Fixed:**
- Meditation said "Largest measured EEG change: Meditation", a ranking of one item.
- Reset always named a winner, even on noise. The ranking now appears only with ≥ 2 measured activities,
  with a note that one session cannot separate small differences from noise.

**Decision:**
- The social probe, the extraversion follow-up and the one-minute EEG profile are complete but have no
  entry card. Restore the cards, or remove the code and README text.

**Suggested:**
- Questionnaires:
  - Show the "I…" stem above IPIP items.
  - Interleave domains and keying.
  - Add an attentiveness check.
  - Rename "Enneagram Personality type predictor" to "Enneagram-inspired reflection".
  - Keep the invented reference bands out of real participants' results.
  - Show the person's own spectrum rather than synthetic participant 0.
- Meditation: sliding-window feedback instead of a cumulative mean.
- Reset: a baseline-to-baseline noise floor.
- Partial questionnaires: show the answered count and offer resume.

## Writing decoder

**Fixed:**
- Writing sessions stopped themselves with a false "EEG signal lost" after a few minutes.
- Cause: while a word was pending, every incoming packet copied and converted the whole 90 s buffer under
  the engine lock, and the page stopped on a single stale poll. Now the engine processes a word only once
  its data are due (ERP epochs the same way), the phrase summary is cached between word changes, and the
  page waits for 3 s of continuous staleness.
- The app's own fallback "Meaning unclear" was masked to "[name] unclear"; it is no longer run through
  name masking.

**Decision:**
- Name masking hides every capitalised word not on a short safe list ("Seven", "Warm"), plus common nouns
  that are also names. That is conservative by design for an audience display. Loosening it trades privacy
  for readability.

**Suggested:**
- Live matches are retrieved from the person's own recent phrases, including the current session. Even
  synthetic noise EEG showed similarities of 0.6–0.85. Say so plainly, or show live matches only from a
  model that passed the held-out test.
- `save_model(..., False)` means "validated" can never be reached; decide whether that is intended.
- Show the gist panel during recording.
- Report "k of n correct (chance 25%, 95% range)".
- List writing sessions in Saved results.
- Unhide "Export recording".
- Check the demo/live state before the instruction gate.

**Not tested:** writing across apps in the native app; the held-out four-choice test, which needs ≥ 2
five-minute holdout blocks.

## Privacy and truthfulness

The audits confirmed that no writing, EEG or embeddings leave the device. The only network code is the
allowlisted account client; ERP upload carries numeric waveforms only; the decoder interest choice uploads
nothing.

Overstated wording to review:
- "Live personality estimates" for a nearest-neighbour demo over invented profiles.
- "Enneagram Personality type predictor".
- "Train alpha power… with live EEG feedback" for a lagging cumulative average.
