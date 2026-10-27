"""Private runtime storage, deliberately outside the distributable source tree."""
import json, os, sys
from pathlib import Path
CODE_ROOT = Path(__file__).resolve().parent

def application_support():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'Bandstand'
    return Path.home() / 'Library/Application Support/Bandstand'

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
    path.chmod(0o700)
    return path

DATA_ROOT = data_directory()
