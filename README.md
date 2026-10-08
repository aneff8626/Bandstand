# Bandstand

A local macOS desktop app for Muse 2 EEG experiments. Open **Muse Lab.app** or double-click **Launch Muse Lab.command** in this folder. Keep the app inside this folder: its source and local Python environment are adjacent to it. Participant data are stored separately.

## Current readiness

- The native app is built and opens successfully. It uses local pipes, not a web-server port, and does not need package downloads to run on this computer.
- Bluetooth runs inside the native app so macOS associates access with Muse Lab. With existing access, it scans and connects automatically at launch. **Connect Muse** initiates setup when access is unavailable. The transport retries disconnected or stalled connections.
- Hardware verified on this Mac: live Muse EEG on TP9, AF7, AF8 and TP10 at 256 Hz, including automatic reconnection after app restart. Physical event timing and signal accuracy remain uncalibrated.
- **Preview synthetic EEG** explicitly enables a simulator. Every simulated recording and report is labeled. The app starts in live mode; it never silently substitutes synthetic EEG for a missing headset.
- Faces/cars and expertise tasks require locally imported photographic sets. Public source links and import controls are provided. No photograph pack is bundled, and no preset is claimed to be an exact replication.
- Optional accounts use Supabase. Recording remains local; research uploads are disabled.

## Workflow

1. Choose ERP, time-frequency, or biofeedback. Choose a protocol and analysis electrodes.
2. Review the source-linked protocol notes, primary analysis window and artifact thresholds. Set display width and viewing distance if visual angle matters.
3. With live EEG available, inspect contact estimates and traces. The app requires recent samples and a clean two-second segment before recording. These estimates are **not impedance measurements**.
4. Start recording. The participant display and analyst plots appear together. Escape or **End session** stops and preserves available data. Leaving the app's presentation tab stops a run if the visibility event is delivered. Gaps or interrupted presentation are flagged.
5. Export raw data/events, processed data, or a PDF. Native-app exports are saved under the private storage directory’s `exports` folder; their absolute path is shown. Saved Sessions exports the full saved session as a ZIP.

## Tasks

| Task | Built-in stimuli | Analysis / limitation |
| --- | --- | --- |
| Visual oddball | Blue/green circles; 25% targets; 800–1200 ms stimulus, 300–500 ms fixation | P300 default TP9/TP10; canonical Pz absent. Based on Krigolson 2017, with documented hardware and preprocessing changes. |
| Auditory oddball | 1000/1500 Hz; equal digital gain; 100 ms tones with 5 ms ramps; 20% targets | N1/P300 teaching adaptation. Physical SPL and audio latency are uncalibrated. This is not ERP CORE's intensity-MMN protocol. |
| Faces/cars | Import ≥20 unique images per condition | 300 ms presentations, 1100–1300 ms gaps. No scrambled controls in this adaptation. Canonical N170 sites are absent. |
| Expertise objects | Import images; choose most/least knowledgeable categories | Birds, dogs, car models, food, plants, instruments, aircraft, chess. Self-report is not an objective expertise test. |
| Flanker | Congruent/incongruent arrows; left/right key responses | Stimulus-locked N2, with accuracy and RT. Does not implement response-locked ERN. |
| Reward | Blue/green square choices; wins/losses | .60/.10 reward probability; randomized positions; feedback-locked AF7/AF8 re-referenced to TP9/TP10. Original color changes across blocks omitted. |
| Eyes open/closed | 8 s rest blocks with tones | Alpha 8–13 Hz, TP9/TP10; primary interval 2–8 s. Posterior sites absent. |
| Rest/arithmetic | Rest vs silent serial sevens | Theta 4–7 Hz, AF7/AF8; primary interval 2–8 s. Fz absent. |
| Custom conditions | User-defined labels/instructions | Configurable band/electrodes; naturalistic confounds must be controlled. No validated effect implied. |
| Biofeedback | Five math problems before/after; 30 s pre/post rest; configurable training | Alpha feedback freezes during artifacts. Power and math accuracy/RT outcomes are reported descriptively. No causal efficacy claim. |

## Processing and statistical interpretation

- Muse 2 nominal 256 Hz, four channels TP9/AF7/AF8/TP10 in microvolts, FPz hardware reference.
- EEG packets are grouped by counter and channel; incomplete groups contain missing values. Counter gaps and wraparound are handled without copying another channel's samples.
- Sample timestamps use the first packet's receive time and nominal sample spacing, with slow bounded drift correction. **BLE transport delay remains uncalibrated.** Reconnection resets the packet clock.
- Browser frame callbacks and Web Audio output-clock estimates are mapped to host time with minimum-RTT clock pings. They are software timestamps, not photodiode/audio-loopback measurements. Raw receive timing and event timing are saved.
- Online ERP processing: causal 60 Hz notch (Q=30), first-order 0.1 Hz high-pass and second-order 30 Hz low-pass. These filters change phase/peak latency; do not treat online peaks as calibrated physiological latency. Raw EEG is retained for offline processing.
- Epoch: -200 to +800 ms; baseline -200 to 0 ms. Signal is interpolated to a common 256 Hz grid only after checking coverage and gaps. Reward trials additionally use the temporal mean as reference.
- Time-frequency: 60 Hz notched EEG; 1 s Hann windows, 125 ms hops, 2–40 Hz, absolute log power. Condition differences are differences of mean log power. Welch-style band features use a periodogram over each nonoverlapping block analysis interval. No hidden baseline division.
- Artifact rules operate on raw EEG. Provisional thresholds flag large amplitude/steps, frontal blink-like changes, elevated 25–45 Hz activity, clipping, flatline, missing samples. Frontal blink flags are applied even when temporal channels are selected. Entire epochs are conservatively rejected, including baseline and the primary interval. No ICA or EOG/EMG validation is claimed.
- ERP display adds condition means and pointwise Student-t 95% intervals from 10 accepted trials per condition. Comparison plots show single trials, then means ± SE.
- Two-sided Welch tests compare trial-level features after every new usable trial, gated by at least 10 usable trials in both conditions (adjustable upward). Exact numeric p, t, df and thresholds for NS/*/**/*** are stored. Repeated looks are uncorrected, trials may be autocorrelated, and one participant's trials do not establish population effects. The threshold of 10 is for display, not a power calculation.
- Biofeedback uses overlapping two-second windows for display. Their summaries are descriptive and are not counted as independent inferential trials. Stable pre/post blocks provide separate features.

## Image controls

Use **Stimulus library** to import images with their publication/source and reuse terms. The importer preserves aspect ratio, fits images within 480 px, pads to 512 px, converts to grayscale and targets digital mean 0.5 and RMS contrast 0.18. It saves achieved values, clipping fraction and the original-file SHA-256. Duplicate original bytes cannot inflate exemplar counts.

These controls do not establish equality of physical luminance, spatial frequency, crop, object pose, identity, familiarity or source-study visual angle. They also do not recreate the full ERP CORE protocol. Use documented original assets for replication work. ERP CORE materials use CC BY-SA 4.0; retain required attribution when importing or redistributing.

## Files and recovery

- `data/<session-id>/continuous.csv`: raw and causal filtered samples, Unix timestamps and source label. Includes three seconds of pre-roll.
- `events.jsonl` and `events.json`: stimulus onset/offset, responses, phases, behavioral trials and timing issues.
- `session.json`: complete plan, random seed, analysis parameters, controls, timing limitations and status.
- `trial-####.npz`: raw, notched, filtered and accepted processed epochs; original relative timestamps and common grid.
- `trials.json`, `analysis.json`, processed ZIP CSVs: trial acceptance/reasons, features, mean ERP, SE, pointwise CI and TF arrays.
- `bandpower.csv`: time, training phase, power, quality status and rejection reasons.
- `report.pdf`: generated on export; simulated recordings are marked prominently.
- `data/desktop.log`: local diagnostic errors. Account credentials are sent only when you use account controls; research recordings are not uploaded.

Raw data and events flush during acquisition. An abrupt process termination may leave `running: true` in metadata, but previously flushed raw/event files remain. Do not interpret that field as proof a session is still recording after a crash.

## Development

Installed runtime is the existing Codex Python 3.12 distribution, exposed through `.venv` with system packages. Required libraries: NumPy, Pillow, ReportLab. macOS native code uses Foundation, CoreBluetooth, AppKit and WebKit; Swift command-line tools must be available to rebuild. No third-party BLE package is needed.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

`server.py` is an optional loopback web frontend on port 8765 for environments that permit a listening socket. The desktop app uses `desktop_service.py` and needs no port. `build/qa/example-report.pdf` is a synthetic pipeline-test artifact, not a human recording. Eleven automated tests passed. A 20-trial desktop simulation completed with 20 accepted trials, saved events/epochs and a PDF exported through the UI. Live hardware remains unverified.

## Primary sources

- [Krigolson et al. 2017: Choosing MUSE](https://pmc.ncbi.nlm.nih.gov/articles/PMC5344886/)
- [ERP CORE and original materials](https://erpinfo.org/erp-core)
- [Luck: ERP CORE N170 design](https://socialsci.libretexts.org/Bookshelves/Psychology/Biological_Psychology/Applied_Event-Related_Potential_Data_Analysis_(Luck)/11%3A_EEGLAB_and_ERPLAB_Scripting/11.04%3A_Design_of_the_N170_Experiment)
- [Rossion et al. 2007: expertise and N170](https://pubmed.ncbi.nlm.nih.gov/17335400/)
- [Gärtner et al. 2015: frontal theta and arithmetic](https://pmc.ncbi.nlm.nih.gov/articles/PMC4403551/)
- [Ishii et al. 2014: rest and mental calculation](https://pmc.ncbi.nlm.nih.gov/articles/PMC4052629/)
- [Muse official hardware comparison](https://choosemuse.my.site.com/s/article/Comparing-Muse-Headbands?language=en_US)
- [Muse-LSL protocol reference](https://github.com/alexandrebarachant/muse-lsl)

## Live artifact attribution and contact display

Large EEG excursions are labeled as EEG transients or possible contact noise, not as evidence of physical movement. Live head movement uses Muse accelerometer variation (>0.035 g RMS over 0.5 seconds) or rotation (>8 degrees/s RMS). These are provisional thresholds, not a validated movement classifier. A muscle label may mention jaw clenching or facial tension as possible causes, never as a confirmed action. Clipping/flatness suppress finer EEG attribution. Trial rejection retains its conservative voltage thresholds.

The contact panel shows estimated signal quality and one-second raw peak-to-peak voltage per electrode. It does not measure impedance. Mind Monitor's developer describes its proprietary SDK horseshoe as based on raw EEG variance: https://mind-monitor.com/forums0/viewtopic.php?t=1840 . This app's estimates do not reproduce that proprietary algorithm. IMU packet scales and layout follow https://github.com/alexandrebarachant/muse-lsl/blob/master/muselsl/muse.py and constants.py.

### Channel-specific live annotations

The outer panel border is removed. Display annotations carry channel IDs and sample-clock onset/offset estimates. Local noise draws translucent boxes and red dotted segments only on affected channels; clean rows retain their colors. A probable blink gets one shared box across the four displayed channels, as a conservative display convention rather than proof of contamination at every electrode.

Live ocular labels require frontal polarity and morphology: a correlated bilateral pulse with recovery for probable blink, an opposed sustained shift for possible horizontal saccade, otherwise an unresolved eye-movement label. Muscle, clipping, flatness or missing data in either frontal channel suppresses ocular attribution. These provisional heuristics have synthetic regression tests, not EOG/eye-tracker validation. Temporal muscle and a separate frontal blink can coexist. Full-epoch trial rejection remains conservative and independent of these display labels.

Reference/ground waveforms are not decoded by this connection; they are explicitly unavailable. The reference is not reconstructed as a zero-valued EEG channel. Relevant sources: https://pmc.ncbi.nlm.nih.gov/articles/PMC3466435/ and https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2020.570419/full .

### Developer calibration and display behavior

Open **Developer tools → Artifact calibration**. Choose each action and record three examples. Each example has 5 s rest and 8 s action. Raw/filtered EEG (.npz), motion packets (.motion.json), action labels, signal features, rest comparison, and provisional annotations (.json) are saved in `data/developer`. Incomplete or gappy examples are flagged. Prompt times are software timestamps and requested actions are not confirmed ground truth. These files support manual revision in a later task; recording does not silently change thresholds.

The live plot runs on a continuous animation clock with a fixed 150 ms playback buffer. Developer tools shows the measured frame rate. Off-scale excursions use dotted horizontal connectors at the row edge; these are display markers, not measured flat voltages. Annotations shorter than 150 ms are hidden in the chart only. Full raw data remains available for trial rejection, and annotation updates are retained in recording exports as `artifact_annotations.jsonl`. Labels extend past event rectangles and wrap only when the plot itself is too narrow.

### Personal calibration revision (2026-10-05)

Five complete recordings, one per requested action, informed `data/artifact_profile.json`. Old capture summaries stored action metrics under the same key as the requested label; the action identity was recovered by exact matching of the saved instruction text to the five defined prompts. New captures store `requested_action` separately. Original recordings are unchanged.

Blink examples were dominated by highly correlated TP9/TP10 excursions. Jaw clench examples increased AF7 amplitude and high-frequency power; horizontal saccades opposed AF7/AF8; vertical gaze tended toward matching frontal polarity; head rotation strongly increased gyroscope magnitude. The revised rules use these patterns and preserve generic contact/noise labels when evidence is insufficient. All personal action attributions carry an asterisk. Up/down gaze included head motion, so both may appear. `data/calibration_replay_review.json` reports descriptive replay only, not independent classification accuracy. More labeled repetitions and an external eye/muscle reference would be needed for validation.

Annotation labels occupy separate collision-free rows above the plot, with matching event numbers in the affected signal regions. Lane space grows when needed and does not collapse every frame. Footnote: “* Signal was unclear.”


## Writing & EEG: temporal decoder and other-app capture

The writing workspace records text labels, edits, first-letter markers, continuous EEG and short display epochs under `data/typing/<session>/`. A separate `.context.npz` for each word holds up to 60 seconds of EEG context as 120 half-second tokens, with per-channel quality weights and relative timestamps. The history selector offers 10, 30 or 60 seconds; the inference cutoff is the first letter or one second afterward. Raw EEG is always retained.

Quality is localized to 250 ms channel segments. Missing/clipped/flat/strongly noisy segments are masked; moderate transients are downweighted. Words remain usable when at least two channels provide enough usable context, including recent context. Overlapping typing is retained and marked. A channel mask is also applied to ERP averages. This replaces the earlier rule that one bad channel or overlapping word rejected the whole trial. `scripts/reprocess_typing_context.py` rebuilds sidecars from existing raw recordings without overwriting original trial logs.

`sequence_decoder.py` implements a trainable PyTorch transformer: two causal encoder layers, four heads, 48 hidden units, learned channel embeddings, sinusoidal encodings of actual relative seconds, and channel/time masks. Every half-second token contains four temporal means, five log band-power features and a variability feature per channel. Text, app identity, key intervals and word lengths never enter this model. Model training uses AdamW with a fixed 24-epoch budget and training-only normalization; candidate vocabulary (up to 12 recurring words) is selected from training labels only. The existing ridge implementation remains a testable baseline, not the live decoder.

Live estimates require ≥30 training and ≥10 later-validation examples per candidate word across ≥8 training and ≥8 later two-minute blocks. A 60-second embargo separates training and validation contexts. The gate checks accuracy, balanced accuracy, a block-level comparison with chance/majority baselines with alpha spending across evaluations, and performance above a mask-only nuisance baseline. Low-margin and out-of-distribution estimates are withheld. These are exploratory within-writer checks; residual motor/eye/muscle and temporal confounds remain, and successful neural word decoding is not established. The checkpoint and review are local. Installed runtime: PyTorch 2.14.1.

`Typing source → Other apps on this Mac` starts a passive native event tap only after Start is clicked and existing Input Monitoring **and** Accessibility grants are confirmed. The app does not request/grant those permissions itself. A visible menu-bar indicator provides Stop & save. Secure input, password/protected fields, terminals, password managers, unsupported field roles, clipboard/paste and modified shortcuts are skipped. No clipboard or field values are read. Focus/cursor changes cancel partial words, and the first partial word after switching fields is skipped until whitespace. Native key reconstruction cannot observe another application's autocorrect or IME replacements. Typed data stays local and capture is never enabled automatically at launch. This mode keeps recording in the background; editor-only recording stops when hidden. System access can be rechecked in the app.

[Apple event-tap documentation](https://developer.apple.com/documentation/coregraphics/cgevent/tapcreate(tap:place:options:eventsofinterest:callback:userinfo:)) · [PyTorch transformer masks](https://docs.pytorch.org/docs/stable/generated/torch.nn.Transformer) · [EEG temporal autocorrelation and evaluation](https://arxiv.org/abs/2405.17024).

### Native capture activation status (2026-10-05)

The new native executable is compiled at `build/next/MuseLab`, but is not installed. Testing showed that its changed ad-hoc code signature no longer matched the existing Bluetooth grant, and Input Monitoring / Accessibility access was unavailable. The installed executable was restored from `build/MuseLab-previous` to preserve existing headset access. Backend transformer and channel-mask changes remain active. Activating across-app capture requires installing the staged executable and user-managed macOS permissions; no permission prompts or settings changes were performed.

### Native capture permissions activated (2026-10-05)

After explicit user confirmation and user authentication, the staged native build was installed, Input Monitoring was added for Muse Lab, and Accessibility was enabled. After Quit & Reopen, Muse Lab reported typing access Ready and live Muse EEG streaming at 256 Hz. Across-app recording remains controlled by Typing source and Start writing & recording.


## Active semantic free-writing decoder (2026-10-05)

The live path now uses `semantic_decoder.py` instead of repeated-word classification. Unprompted writing is grouped into non-overlapping 3–12-word phrases, split at punctuation, pauses over five seconds, invalid edits and recorded focus boundaries. Context features come from the first word, ending at the configured cutoff (default first-letter onset). Historical recordings without focus IDs only have session/pause boundaries available.

A frozen local `sentence-transformers/all-MiniLM-L6-v2` encoder (revision in `models/all-MiniLM-L6-v2/revision.txt`) supplies 384-dimensional targets. Text never enters the EEG predictor. A regularized linear map uses masked EEG summaries across eight time intervals, replacing the more expensive trainable transformer. Training reads each compressed context file individually. Results retrieve up to three previously recorded training phrases; they are not generated sentences or calibrated word probabilities. Unvalidated matches are labeled. Evaluation uses later unseen phrases, a 60-second embargo, and mean-target, previous-text and mask-only baselines; recording-block sign tests use alpha spending. No claim of neural language decoding is made.

Resource policy: latest 3,000 word records in memory, at most 512 phrases per fit and 256 retrieval candidates, eight texts per embedding batch, one compute thread, a separate worker with a 1.5 GiB peak-RSS watchdog checked every 0.5 seconds and a 180-second parent timeout. The watchdog can briefly overshoot its threshold; this is not an OS-wide RAM cap. Training attempts are at least five minutes and 100 new words apart until the rolling window is full. All prior trial files stay on disk. New continuous files are lossless `continuous.csv.gz`; exports include these without expansion. Recording stops if free disk drops below 10 GiB (checked every ten seconds), without deleting data. Existing CSV recordings are preserved. The frozen text model is loaded only in the training worker and runs offline; no text or EEG is uploaded.

Validation: semantic boundary/masking, train-only retrieval bank, gzip roundtrip and bounded row retention tests, plus the existing acquisition suite. The pretrained model was downloaded once from its official Hugging Face repository and its embedding output checked locally.

### Live tentative phrase display

A provisional EEG-to-semantic model is now fitted after eight usable phrases with four distinct texts, before the validation gate. It remains explicitly unvalidated. Live matches refresh once per second from the trailing EEG context, with three retrieved alternatives and cosine similarities. They are earlier writing excerpts, not generated next sentences. Held-out validation still uses a separate earlier/later split and is never replaced with training accuracy. Continuous sliding-window inference is exploratory and differs from the word-onset evaluation distribution. Poor-quality/out-of-distribution EEG abstains.


## Bandstand privacy and accounts (implementation status)

Private recordings are stored outside the code folder. `BANDSTAND_DATA_DIR` or ignored `local-settings.json` can override the default `~/Library/Application Support/Bandstand/data`. Keep local settings, recordings, logs, exports, imported stimuli, personalized models and phrase banks out of source releases. Local files are not application-encrypted.

Enrollment supports optional Supabase email/password accounts. Passwords are never intentionally persisted by Bandstand; tokens are held in process memory. The authentication client sends only allowlisted credentials to the fixed project endpoint and does not follow redirects. Local recording does not require an account. Account deletion removes the signed-in cloud account and its consent row; local recordings remain. Provider backups are not erased immediately.

ERP sharing preferences are local requests only. Research uploads and shared decoder contributions remain disabled. There is no secure aggregation or differential privacy implementation yet. Do not upload personal decoder files: they may contain readable phrase libraries. Backup expiration policy must be finalized before research enrollment is released.

`hosting/` is a minimal coordinator deployment scaffold. Build only that directory as the Docker context. `/health` reports readiness; all POST requests are rejected. It is not a functioning federated training service.

Run `python scripts/audit_release.py` to construct and scan the explicit source review bundle. This checks selected text and credential patterns, not every possible source of sensitive information. Review dependencies, licensing and package assets before public release.

### Accounts and email delivery

GitHub hosts source and a static information site. Supabase handles authentication. Account creation, sign-in and password recovery are inside the local app. Recovery accepts an emailed recovery code, or a copied unopened Supabase recovery link. The local service validates the recovery proof with Supabase before updating the password. Do not enter passwords on GitHub Pages. The old standalone password page is not part of the release.

Custom SMTP must be configured in Supabase before inviting participants. Its default service restricts email delivery to project team addresses. Configure recovery emails to show `{{ .Token }}` for convenient in-app entry. Keep email verification enabled. SMTP credentials belong only in Supabase settings. Actual email confirmation, recovery, expired/reused links and delivery still need a designated test account. Automated tests use synthetic values and mocked requests.

Research uploads and cloud consent synchronization remain disabled. This is a source preview, not completed participant enrollment or shared learning. Supabase cannot recover lost local recordings or a lost email inbox. Provider backup retention must be defined before sharing opens.

## License and contact

Bandstand source is MIT licensed, copyright 2026 Andrew Neff. Research contact: aneff8626@gmail.com. Downloaded models and imported stimulus sets retain their own licenses.

For a fresh source checkout, create `.venv` with Python 3.12 and install `requirements.txt`. The writing semantic encoder additionally needs sentence-transformers and its separately downloaded model; it is not bundled in the public source. Build the native macOS app using the launch script and installed Apple command-line tools. A clean-machine installation test remains pending.
