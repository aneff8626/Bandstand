#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ ! -x '.venv/bin/python' ]]; then
  echo 'The local Python environment is missing. See README.md.'
  exit 1
fi
# Launching must never rebuild the permission-bearing native executable.
if [[ ! -x 'Muse Lab.app/Contents/MacOS/MuseLab' ]]; then
  echo 'The signed desktop app is missing. Install a signed Bandstand build; launching does not compile a new identity.'
  exit 1
fi
open 'Muse Lab.app'
