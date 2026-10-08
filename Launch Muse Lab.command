#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ ! -x '.venv/bin/python' ]]; then
  echo 'The local Python environment is missing. See README.md.'
  exit 1
fi
mkdir -p build 'Muse Lab.app/Contents/MacOS'
if [[ ! -x 'build/muse-bridge' ]]; then
  /usr/bin/swiftc -module-cache-path build/module-cache native/MuseBridge.swift -o build/muse-bridge -framework CoreBluetooth -framework Foundation
fi
if [[ ! -x 'Muse Lab.app/Contents/MacOS/MuseLab' ]]; then
  /usr/bin/swiftc -module-cache-path build/module-cache native/Desktop.swift native/MuseTransport.swift native/TypingMonitor.swift -o 'Muse Lab.app/Contents/MacOS/MuseLab' -framework AppKit -framework WebKit -framework CoreBluetooth -framework ApplicationServices -framework Carbon
fi
open 'Muse Lab.app'
