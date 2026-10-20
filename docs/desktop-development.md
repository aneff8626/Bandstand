# Editable desktop development

Install **contributor build 8 or later** (Apple Silicon, macOS 14+). It is a signed, notarized desktop shell with native Bluetooth and typing bridges. Web/Python source can come from your checkout; a browser preview cannot provide those native bridges.

## First setup

1. Download the desktop ZIP from the README, unzip, and drag Bandstand.app into Applications. Quit other Bandstand windows before using the headset.
2. Clone and select the shared integration branch:
   ```sh
   git clone https://github.com/aneff8626/Bandstand.git
   cd Bandstand
   git checkout codex/desktop-release
   ```
3. Copy `backend.development.example.json` to `backend.json`. The example points to local Supabase at port 54321. Start your local Supabase stack and replace the placeholder with its **publishable client key**. The example is not a running backend. Local EEG work can start without a reachable account server; signup/sharing tests need the server and migrations.
4. For a shared staging Supabase project, use `"name": "staging"`, its `https://<project-ref>.supabase.co` URL, and its publishable client key instead. Apply reviewed migrations to staging before testing account/sharing features. Production is refused, including a production URL mislabeled as staging. `backend.json` is gitignored. Never use a service-role/secret key or real participant data.
5. With a system Python 3 available, run:
   ```sh
   python3 scripts/launch_development.py
   ```
   The launcher links the checkout’s gitignored public text encoder to the bundled copy if absent, so writing-decoder development needs no extra model download. No Python dependencies need to be installed for the launcher; the desktop shell uses its **bundled** Python runtime. Pass `--app /path/to/Bandstand.app` to select another installed copy, or `--check` to validate without launching.

The window says **Bandstand · Development**. Data goes to `~/Library/Application Support/Bandstand Development/data`; production recordings and saved sign-ins are separate. Development sign-ins are additionally separated by backend URL. A normal app launch uses bundled code, the production backend, and the normal data directory. Never replace files inside the installed signed app.

## Collaboration

All PRs target **`codex/desktop-release`** and desktop releases are cut from that branch. Each contributor should use a separate feature branch and merge reviewed PRs into the shared branch. To receive merged work:

```sh
# Commit or stash your own edits first.
git checkout codex/desktop-release
git pull --ff-only
python3 scripts/launch_development.py
```

Quit and relaunch after changes. Web and compatible Python edits appear without a new download. Swift/native bridge changes, incompatible native-interface changes, or new/changed Python dependencies require a new signed contributor build. The launcher warns if requirements differ from the bundled manifest or installed package versions. Do not pip-install into the app bundle.

Editable code runs with the app's permissions. Only launch trusted, reviewed checkouts. Notarization covers the installed shell, not arbitrary checkout code. Contributors do not need Andrew's signing certificate; never share it.

## Release and acceptance checks

The builder runs `scripts/smoke_development.py` against the actual packaged executable: a temporary checkout marker must appear through WKWebView, the runtime must be bundled, the window title/data path must be development-specific, and production configuration must be rejected. Unit tests cover launcher rejection and normal backend/session defaults. The smoke flag suppresses automatic Bluetooth connection; it is for build checks only.

Before publication: run automated tests, sign with the persistent Developer ID, notarize, staple, and verify Gatekeeper. On a **second Mac**, Nideesh must verify:

- Install the download, open normally, and confirm bundled startup/account behavior.
- Clone, configure development/staging, and launch with the script.
- Edit `web/style.css`, quit and relaunch; see the change without downloading another app.
- Confirm Bluetooth and typing permissions work in contributor mode.
- Confirm production configuration is refused and ordinary launch remains unchanged.

Second-Mac and physical-headset checks cannot be claimed from a local packaged smoke test.
