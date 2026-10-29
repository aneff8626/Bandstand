"""Private runtime storage, deliberately outside the distributable source tree."""
import json, os, sys
from pathlib import Path
CODE_ROOT = Path(__file__).resolve().parent

def application_support():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'Bandstand'
    return Path.home() / 'Library/Application Support/Bandstand'

def restrict_windows_directory(path):
    """Use an inheritable Windows ACL; chmod's POSIX mode bits do not protect Windows files."""
    import csv, re, subprocess
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, text=True, check=True, creationflags=flags)
    sid = next(csv.reader(result.stdout.splitlines()))[-1].strip()
    if not re.fullmatch(r'S-1-[0-9-]+', sid): raise ValueError('Cannot determine the current Windows user')
    subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                    '*' + sid + ':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                   capture_output=True, check=True, creationflags=flags)

def data_directory():
    config = application_support() / 'local-settings.json'
    if not config.exists():
        config = CODE_ROOT / 'local-settings.json'
    settings = json.loads(config.read_text()) if config.exists() else {}
    path = Path(os.environ.get('BANDSTAND_DATA_DIR') or settings.get('data_dir') or
                application_support() / 'data').expanduser().resolve()
    if path == CODE_ROOT or CODE_ROOT in path.parents:
        raise ValueError('Private storage must be outside the application code folder')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'nt': restrict_windows_directory(path)
    else: path.chmod(0o700)
    return path

DATA_ROOT = data_directory()
