import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from utils import hv_flow_audit as audit
class StatusSave(unittest.TestCase):
 def test_transient_windows_lock_is_retried(self):
  original=Path.replace
  attempts=[]
  def replace(path,target):
   attempts.append(1)
   if len(attempts)==1:raise PermissionError('simulated reader lock')
   return original(path,target)
  with tempfile.TemporaryDirectory() as d,patch.object(Path,'replace',replace),patch.object(audit.time,'sleep'):
   p=Path(d)/'progress.json';audit.save(p,{'t':50})
   self.assertEqual(json.loads(p.read_text()),{'t':50});self.assertEqual(len(attempts),2)
 def test_persistent_write_failure_is_not_hidden(self):
  with tempfile.TemporaryDirectory() as d,patch.object(Path,'replace',side_effect=PermissionError('locked')) as replace,patch.object(audit.time,'sleep'):
   with self.assertRaises(PermissionError):audit.save(Path(d)/'progress.json',{'t':50})
   self.assertEqual(replace.call_count,10)
