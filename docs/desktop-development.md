# Editable desktop development

A browser preview does not contain the native Bluetooth or macOS typing bridge. Use an installed contributor desktop build with a local source checkout. This preserves the signed native executable while allowing Python and web edits.

1. Install the contributor build in Applications. Quit other Bandstand windows so only one process owns the headset.
2. Clone the repository and check out the integration branch. Install Python dependencies for local tests.
3. Create an ignored `backend.json` with exactly `name`, `url`, `publishable_key`, pointing to staging or local Supabase. `backend_config.py` validates these values. Never put a service-role key here.
4. Run `python scripts/launch_development.py`. The native shell uses its bundled Python runtime and reads this checkout. Restart after Python edits; reload/relaunch after web edits. Native Swift changes still require a newly signed build.
5. Development data is isolated under `~/Library/Application Support/Bandstand Development/data`. Ordinary app launches use bundled code and the normal private data directory. Do not copy production participant archives into the checkout.

The current public v0.3.0-alpha.1 source release does not guarantee this shell option exists in an older installed binary. Install a build containing this change before using the launcher. Developer code executes with the app's existing permissions: use only a reviewed checkout, never an untrusted PR. Andrew's private signing certificate is not needed for web/Python iteration and must not be shared.

## Desktop release test

Build with a persistent Developer ID certificate and version/build number. Verify code signature, notarize/staple and assess Gatekeeper. Test the downloaded artifact on another Mac, including account recognition after reopening and permission retention after an update. A local successful launch or signature check is insufficient evidence for a clean install.
