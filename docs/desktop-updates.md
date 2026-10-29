# Desktop updates and release ownership

## For contributors

Work in `aneff8626/Bandstand`; target `codex/desktop-release`. The app stays editable through the development launcher. Normal installed macOS builds include Sparkle update checks and a **Bandstand → Check for Updates…** menu item. An update asks to install and relaunch; it must wait until recording and model training finish. Development launches do not run the release updater.

The initial updater-enabled version requires one manual download. Existing older builds cannot acquire an updater they do not contain. Windows remains a portable preview with manual downloads for now; this implementation adds macOS updating only.

## Signing boundary

`Desktop Candidate` CI tests and builds unsigned artifacts with read-only repository permissions and no Apple secrets. The private `aneff8626/Bandstand-Releases` repository validates the candidate and signs/notarizes it without executing its code. Only Andrew currently has access to that repository. It publishes accepted, stapled, Gatekeeper-verified archives back to the main repository and advances the update feed. The dedicated Sparkle private key is stored only in that private repository and the owner's Keychain; only the public key ships in the app.

Contributors can change application behavior through merged code. This separation protects signing credentials; it does not substitute for reviewing application changes.

## Acceptance checklist — October 29, 2026

- [x] Fresh production signup using the ordinary app account handler and a new alias of the authorized test inbox.
- [x] Confirmation email arrived in inbox; code verification and password sign-in succeeded without administrator confirmation. Test session signed out afterward.
- [x] Private signing repository created; owner-only access verified.
- [x] Dedicated updater key generated and private repository secret configured.
- [x] Mac updater compiles; development mode excludes updater.
- [x] Recording/training guards and idle reservation tests pass.
- [x] 237 Python tests and 30 JavaScript tests pass.
- [x] Unsigned candidate builds; bundled runtime/offline encoder and packaged development-window smoke pass.
- [x] Source-only publication audit passes, including comparison against local private strings.
- [x] Private archive path/symlink validation tests pass.
- [ ] Owner supplies dedicated Apple notarization API credentials and Developer ID certificate export to the private repository.
- [ ] Owner supplies a narrowly scoped main-repository release token (Actions read, Contents write) to the private repository.
- [ ] CI build and private signing workflow complete successfully against the integration branch.
- [ ] New release passes notarization, stapling and Gatekeeper. Current saved local notarization profile returned HTTP 401; no acceptance claimed.
- [ ] Install older/newer updater-enabled notarized builds and verify actual upgrade, preserved local data and permissions, offline startup, invalid-update rejection, and recording deferral.
- [ ] Enable automatic release polling only after the preceding checks pass.

No new downloadable release is claimed by the code checks above. Keep the known installed app until a verified replacement is available.

## Signup troubleshooting

The October 28 failures were Gmail SMTP error 535 (invalid stored credentials), not a missing Supabase paid plan. Replacing the Gmail app password fixed delivery. If signup fails again, tell your Chat to inspect the app error and Supabase Authentication logs for the timestamp, then check SMTP authentication, rate limits and the confirmation template. A successful resend response alone does not prove mail delivery. Do not manually confirm the user as a substitute for fixing signup.

Do not share passwords, confirmation codes, refresh tokens, private writing, or EEG recordings in troubleshooting reports. Include the app version/build, operating system, timestamp, action, and redacted error.
