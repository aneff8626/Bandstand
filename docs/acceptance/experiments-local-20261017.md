# Experiment fixes — local verification, 2026-10-17

Browser preview of branch `experiments` on synthetic EEG, driven by puppeteer. The scripts are in
`build/ui/` (not committed; they depend on local paths).

## Simulated effect directions (`check_demo_effects.mjs`)

| Task | Trials/blocks | Channel results (t, p) | Expected | Outcome |
|---|---|---|---|---|
| Visual oddball | 60 | TP9 −13.2 (1.6e-11); TP10 −13.0 (1.2e-14) | target > standard | pass |
| Faces & cars | 40 | TP9 −4.1 (2e-4); TP10 −5.3 (5.5e-6) | faces more negative | pass |
| Flanker | 40 | AF7 +2.5 (.016); AF8 +2.7 (.0098) | incongruent more negative | pass |
| Reward | 40 | AF7 −11.3 (5.6e-12); AF8 −8.2 (5.7e-10) | win > loss | pass |
| Eyes open/closed | 20 | TP9 −8.4; AF7 −4.5; AF8 −4.4; TP10 −7.0 (all p < .001) | closed > open | pass |
| Rest & arithmetic | 20 | AF7 −14.9; AF8 −14.3 | arithmetic theta > rest | pass |
| Biofeedback | 6 + 6 blocks | t = 0.11, 0.37, 0.76 across runs; all NS | no injected effect | pass |

## Screen checks

| Check | Outcome |
|---|---|
| Faces Setup shows image counts and opens the library; importing 20 + 20 makes it ready | pass |
| Audio gain 3, empty and 0 refused before recording; the engine refuses 3; 0.04 starts | pass |
| No condition tally on the participant screen in oddball; tally hides when the EEG panel collapses | pass |
| "Your own conditions" and "Alpha training & behavior" offered | pass |
| Flanker Task behaviour table (accuracy, errors, misses, median RT, congruency effect) | pass |
| Reward Choice behaviour table; plan has no pre-drawn outcome; choice RT summarised | pass |
| New run starts promptly after Escape during a reward choice (3.8 s, including navigation) | pass |
| Without an account, "No" sharing choices save locally | pass |
| Biofeedback: 6 + 6 rest blocks, comparison ready, Math performance with pre and post, ERP plot hidden, no stale countdown | pass |

## Writing lag (`writing_lag.mjs`, 7 minutes each, synthetic live bridge)

| Build | Words | EEG lag over time | Max |
|---|---|---|---|
| Before (app-edits) | 941 | ≈0.03 s, then 0.36 → 0.55 → 0.72 s after ~850 words | 0.75 s, rising |
| After (experiments) | 942 | 0.01–0.06 s throughout | 0.21 s |
