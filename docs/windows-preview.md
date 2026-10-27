# Windows preview — implementation and acceptance checklist

## Student setup

This preview targets Windows 10/11, x64. Download and **extract the entire ZIP** to a writable folder, then double-click **Launch Bandstand.cmd**. Keep `app` and `runtime` together. Python and the public text encoder are bundled; no Python installation, terminal commands, headset, or account are required. The command launcher briefly opens a console before opening the desktop window.

Microsoft Edge WebView2 Runtime is required. If the startup dialog reports it missing, install the Evergreen runtime from https://developer.microsoft.com/microsoft-edge/webview2/. This preview has no Windows code-signing certificate; Windows security software may warn or block it. Do not disable system security to run it.

Continue without an account. Synthetic EEG starts explicitly in a window labeled **Windows Preview · Synthetic EEG**. Follow Activity → Setup → Run → Results. Include **Test sessions** in Results filters. Some experiments require imported images. The writing editor works inside Bandstand; synthetic EEG cannot establish real decoder performance. Personality EEG outputs remain synthetic demonstrations.

Data are stored under `%LOCALAPPDATA%\Bandstand Windows Preview\data`, separately from future real recordings. Writing and embeddings stay local. Remembered sign-ins use Windows Credential Manager. Muse Bluetooth is experimental; typing across other applications remains unavailable. This preview does not activate shared decoder training.

## Build

Run the **Windows Preview** GitHub Actions workflow, or on Windows with Python 3.12 x64 run `python scripts/build_windows.py` after installing `requirements-windows.txt`. The workflow tests the source, audits publication contents, builds from the explicit audited source bundle, bundles official embedded CPython, verifies the pinned public encoder, and tests the packaged runtime. Download the workflow artifact and extract its inner application ZIP. CI artifacts expire after 14 days; publish only a tested artifact as a GitHub release.

Python uses its isolated `_pth` file; account keys, recordings, private models, developer environments, and local configuration are not copied. The app uses an ephemeral loopback port with a launch cookie, Host/Origin checks, and the existing per-launch POST token. It has no remotely listening service. No native JavaScript bridge is exposed.

## Checklist

- [x] Windows launcher and dedicated desktop window using WebView2.
- [x] Explicit synthetic acquisition; experimental Muse Bluetooth; unsupported cross-app typing disabled.
- [x] Isolated preview data folder and synthetic labels for writing sessions.
- [x] Windows Credential Manager integration; no plaintext password fallback.
- [x] Portable memory check for local semantic training.
- [x] Audited packaging, bundled Python/dependencies/public encoder, checksum.
- [x] Windows CI build with packaged backend and offline-encoder smoke checks.
- [x] Windows CI passes on packaged code commit `88e1b61` (run 40540970510): 231 Python tests, 30 JavaScript tests, bundled backend, offline encoder, and real WebView2 startup.
- [x] Windows runner renders the app and supports continuing without an account; synthetic label and unavailable Bluetooth verified.
- [ ] Fresh Windows computer: extract, launch, enrollment/local continuation, restart.
- [ ] WebView2 visual interaction: experiment start/stop, audio, imports, plots, exports.
- [ ] Save and reopen ERP, spectral, questionnaire and writing records.
- [ ] Verify real Windows sign-in persistence/logout with an ordinary test account.
- [x] Windows preview 1 published from the tested package (see release link below).
- [ ] Native installer/shortcut and Windows code signing.
- [ ] Real Muse Bluetooth hardware validation (transport implemented; not yet headset-tested).
- [ ] Cross-app Windows writing capture and privacy/permission review.

The checked entries indicate implemented code, not second-computer acceptance. Windows hardware, graphical interaction, and account delivery must be verified separately. Update this checklist as evidence arrives.

## Windows preview 1

[Download](https://github.com/aneff8626/Bandstand/releases/tag/v0.3.0-windows-preview.1) · [Windows CI evidence](https://github.com/aneff8626/Bandstand/actions/runs/40540970510). The first-PC acceptance items above remain open.

## Experimental Bluetooth (preview 2)

Choose **Connect Muse · experimental** in Headset. Turn Windows Bluetooth on, keep one Muse nearby, and close other apps connected to it. No pairing-code workflow is required by Bandstand. Scanning takes about eight seconds; connection may take another fifteen. The app displays scan, connection, missing-device and stream-timeout status. Disconnect stops acquisition; reconnect begins a fresh stream. Stop recordings before changing sources. Use the synthetic EEG toggle to return to demos.

This uses the same four-channel Muse packet format and p21 preset as the Mac transport, through Bleak's Windows backend on a background thread. Hardware compatibility, adapter reliability and Windows Bluetooth permissions still need testing on a real PC. Motion and pulse are not yet supported by this Windows transport. The preview continues to store records in its separate local folder; real sessions are labeled live, synthetic sessions simulation.

Preview 2: [Download experimental Bluetooth build](https://github.com/aneff8626/Bandstand/releases/tag/v0.3.0-windows-preview.2). Windows CI run 40556817290 passed 234 Python tests, 30 JavaScript tests, packaged service/WebView2 startup and offline encoder. Physical headset testing remains outstanding.
