import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import private_storage
class UserStorageTests(unittest.TestCase):
 def test_user_config_survives_bundle_replacement_and_dev_env_wins(self):
  with tempfile.TemporaryDirectory() as directory:
   home=Path(directory).resolve();code=home/'app';code.mkdir();data=home/'existing';dev=home/'development'
   config=home/'Library/Application Support/Bandstand/local-settings.json';config.parent.mkdir(parents=True);config.write_text(json.dumps({'data_dir':str(data)}))
   with patch.object(private_storage,'CODE_ROOT',code),patch.object(Path,'home',return_value=home),patch.dict('os.environ',{},clear=True):
    self.assertEqual(private_storage.data_directory(),data)
    with patch.dict('os.environ',{'BANDSTAND_DATA_DIR':str(dev)}):self.assertEqual(private_storage.data_directory(),dev)
