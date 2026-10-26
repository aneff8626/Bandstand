# Custom experiments

Learn about your brain groups activities into Steady state and Event-related. Both include Custom experiment. Custom conditions is a collapsed, optional setup button containing 2–4 condition names and optional per-condition instructions. Without editing, Condition 1 and Condition 2 are presented. Response-key configuration is removed. Timing, repetitions, condition order and breaks are collapsed under Advanced controls. Existing ERP settings remain collapsed.

Steady-state defaults: 12-second blocks, two-second intervals, 10 repetitions per condition, alternating order. Analysis excludes the first two seconds and uses the existing channel-local spectral rejection and block estimates. Custom order lists every condition once and repeats that order; randomized order shuffles the balanced list.

Event-related custom experiments are labeled Ultra-tentative. Import PNG/JPEG/WebP images or uncompressed PCM WAV audio (mono/stereo, up to 30 seconds, 12 MB/file). Files are decoded/validated and stored privately under stimuli; images are resized without changing aspect ratio. Media are optional: conditions without files display their names as text. Media preload before trials. Each condition cycles through its supplied files. Defaults: 800 ms presentation, 1200 ms interval, 20 presentations per condition, randomized balanced condition order. Audio uses the configured gain, capped at 0.2 and stops at the configured presentation duration. Video is deferred. Software frame/audio onset timestamps are estimates; no physical latency calibration is implied.

New custom sessions do not record named response keys. Historical response events remain readable.

All conditions appear separately per electrode. For two conditions the existing exploratory Welch comparison applies. Three/four conditions show descriptive results without an omnibus or pairwise significance claim. Imported media, custom names/instructions and response events remain local; the shared ERP allowlist excludes both custom protocols. A clean appearance is not validation of a custom experimental design.
