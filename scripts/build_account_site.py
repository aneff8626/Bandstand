"""Build a static GitHub Pages information site. Never handles credentials."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'docs'
out.mkdir(exist_ok=True)
(out/'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Bandstand</title></head><body><main><h1>Bandstand</h1><p>Local EEG experiments and exploratory writing research for macOS and Muse headsets.</p><p><a href="https://github.com/aneff8626/Bandstand">Download source and installation instructions</a></p><h2>Accounts</h2><p>Create an account, sign in, or reset your password inside Bandstand. This website does not accept passwords or recovery codes.</p><h2>Privacy</h2><p>Writing, EEG, embeddings and personal decoders stay on the participant’s computer. Research uploads and shared learning are disabled in this preview. Accounts are managed by Supabase.</p><p>Research contact: <a href="mailto:aneff8626@gmail.com">Andrew Neff</a></p><p>MIT licensed. Research software; decoder performance is exploratory.</p></main></body></html>')
(out/'.nojekyll').touch()
print('Public information site prepared; no passwords, account tokens, or research data.')
