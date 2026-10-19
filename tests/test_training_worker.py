import unittest
from unittest.mock import patch
from queue import Queue
import shared_learning

class WorkerFailureTests(unittest.TestCase):
 def test_priority_and_database_failure_return_without_sensitive_message(self):
  out=Queue()
  with patch('os.nice',side_effect=PermissionError()),patch('cumulative_semantic.connect',side_effect=ValueError('private-writing-canary')):
   shared_learning._child('unused',{},None,None,None,out)
  self.assertEqual(out.get_nowait(),('error','ValueError'))
