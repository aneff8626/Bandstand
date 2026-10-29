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
- [x] Dedicated Apple notarization API credentials and Developer ID certificate export configured and validated in the private repository.
- [x] Main-repository-only release token configured (Actions read, Contents write; expires October 29, 2027).
- [x] Integration candidate and hosted signing/notarization passed for build 400; published baseline installed and native update-feed check passed.
- [x] Owner refreshed the local notarization Keychain profile; Apple authentication now succeeds.
- [x] Local build 200 passed Apple notarization, stapling, strict code-signature verification and Gatekeeper. Submission: `ee73661e-818f-4eac-9078-4a8b74c2334f`. The archive is prepared locally, not published.
- [x] Final ZIP extracted into a temporary installation directory and passed signature, staple and Gatekeeper checks there too.
- [x] Final archive signed with the dedicated updater key; public-key verification, byte length and SHA256 match. A deliberately altered archive fails signature verification. Local feed and provenance files are prepared; neither is published.
- [x] Downloaded published build 400, installed it, and upgraded to build 600 through the native Sparkle UI. Download, extraction, Install and Relaunch, and About Bandstand (600) verified.
- [x] All 12,997 pre-existing local data files retained identical SHA256 hashes; signed-in account remained recognized. No new permission prompts appeared. Hardware permission continuity still needs a real headset/typing check.
- [x] During a synthetic recording, update check was refused until recording finished. Returned app to normal headset mode afterward.
- [x] Installed build 600 passes strict deep code-signature verification, stapler validation, and Gatekeeper after relaunch.
- [ ] Fresh offline-machine launch, hardware reconnection/typing permissions, and end-to-end deliberately invalid feed installation still need separate checks; archive tamper rejection was verified cryptographically.
- [ ] Enable automatic release polling only after the preceding checks pass.

Build 400 is the first published updater-enabled baseline; [build 600](https://github.com/aneff8626/Bandstand/releases/tag/v0.3.0-build600) is the verified current download. Hosted release run: `40904067490`; source commit: `9fb19c227e3227e1a9e35c76beb6f909a42015af`. Update checks do not automatically download or install; the user chooses installation and relaunch.

## Signup troubleshooting

The October 28 failures were Gmail SMTP error 535 (invalid stored credentials), not a missing Supabase paid plan. Replacing the Gmail app password fixed delivery. If signup fails again, tell your Chat to inspect the app error and Supabase Authentication logs for the timestamp, then check SMTP authentication, rate limits and the confirmation template. A successful resend response alone does not prove mail delivery. Do not manually confirm the user as a substitute for fixing signup.

Do not share passwords, confirmation codes, refresh tokens, private writing, or EEG recordings in troubleshooting reports. Include the app version/build, operating system, timestamp, action, and redacted error.
