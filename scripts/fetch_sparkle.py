"""Fetch the pinned official Sparkle distribution; never run downloaded scripts."""
import hashlib
from pathlib import Path
import subprocess
import urllib.request

VERSION = '2.10.1'
SHA256 = '1a856d2a9edb8e628de88121d7be04cf0e2167f8641650b78fca00b14244cf27'
URL = f'https://github.com/sparkle-project/Sparkle/releases/download/{VERSION}/Sparkle-{VERSION}.tar.xz'
PUBLIC_KEY = 'jFuGoTrLfNfKxai6Nm1DeGEOHZwPXBNFbOqSrkd/L5o='
FEED = 'https://github.com/aneff8626/Bandstand/releases/download/updates/appcast.xml'


def fetch(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / f'Sparkle-{VERSION}.tar.xz'
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            archive.write_bytes(response.read(32 * 1024 * 1024))
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Sparkle download checksum mismatch')
    destination = root / VERSION
    if not destination.exists():
        destination.mkdir()
        subprocess.run(['/usr/bin/tar', '-xf', str(archive), '-C', str(destination)], check=True)
    return destination


if __name__ == '__main__':
    print(fetch(Path(__file__).resolve().parents[1] / 'build/sparkle'))
