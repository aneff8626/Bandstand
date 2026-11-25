# Experimental P300 direction cursor

Four arrows (↑ → ↓ ←) surround a 7 × 7 grid. Each move flashes every arrow ten times in random order; the participant silently counts the flashes of the arrow pointing toward the gold target square, and the dot moves one cell in the arrow the classifier selects. It reuses the speller's per-electrode decoder, so the same timing, validation and interpretation limits apply. See [p300-speller.md](p300-speller.md).

## Try it

Open **Activity → BCI → P300 direction cursor → Setup → Start activity** with EEG streaming. Count the flashes of each cued arrow for eight calibration moves (about two minutes). Then press **Reach a target**: a gold square appears three to five cells away and moves repeat until it is reached, the move limit (twice the fewest possible moves plus four) is used, or **Pause after this move** is pressed. **Add 4 calibration moves** retrains with up to 24 moves. **End & save** or Escape saves locally and opens Results.

Each move takes about 15 seconds: two seconds to get ready, 40 flashes of 120 ms at about 300 ms onset intervals, and 1.1 seconds for the last responses. The same arrow never flashes twice in a row. Hidden display, interrupted timing or stale EEG stops the task. Stop if flashing is uncomfortable.

## Decoder

Calibration cues each arrow equally often in blocks of four. For every usable electrode, the speller's nested held-out search chooses a 100–400 ms interval within 100–800 ms, using whole held-out calibration moves instead of letters, and fits a shrinkage discriminant on 50 ms mean amplitudes. Electrode scores are averaged per flash. A move needs at least three clean flashes of every arrow; otherwise the dot stays put and the reason is shown. The winning arrow has the highest mean score. The **arrow gap** (winner minus runner-up) is classifier evidence, not a probability.

Free moves send no target label: the engine rejects cursor-move flashes that carry a target or an attended condition, as it does for spelling. The target square and position are sent only after the flashes, to record the move.

## Measures

- **Held-out calibration accuracy:** each calibration move is predicted by a decoder trained without it. Chance is 25%. The readiness rule matches the speller (held-out AUC ≥ 0.65, above chance in ≥ 75% of moves, ≥ 50% of moves correct).
- **Bits per minute:** the Wolpaw information-transfer rate for a four-choice selection at the held-out accuracy, at the fixed pacing of about 15 seconds per move. It is a calibration summary, not a measured rate during free steering, where the intended arrow is unknown.
- **Moves toward the target:** a move counts if it reduced the distance to the target. A random move helps with probability (number of arrows that would help) / 4, which is 1/4 on a straight line and 1/2 on a diagonal; the expected number of helpful random moves is reported alongside.
- **Targets:** reached or not, with moves used and fewest possible.

Results show calibration responses per electrode with each electrode's learned interval, exactly as for the speller; free-move flashes never enter those ERPs or point statistics. The cursor is excluded from ERP sharing.

## Simulation

The simulator adds a P300 to cued calibration arrows only, so calibration can be rehearsed without a headset. It cannot know the intended arrow during free moves, so simulated free moves are random and labelled as such.

## Interpretation limits

Muse sites (TP9, AF7, AF8, TP10) miss the central and parietal sites where the P300 is usually largest, so separation may be weak. With four arrows the attended arrow flashes once in four, which is less rare than in the speller (one in six) and can reduce the response. Repeated flashes overlap within the 800 ms epoch. Software timestamps leave physical display and Bluetooth latency uncalibrated. Eight calibration moves give only a rough check; Muse cursor accuracy is unvalidated.
