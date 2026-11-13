import unittest
import tempfile
from pathlib import Path
from utils.navigation_followup import demand, gate, verify_hashes
class ProtocolTests(unittest.TestCase):
 def test_demand_conserves_entry_capacity(self):
  self.assertEqual(demand({'a':['x','y'],'b':['x','z'],'c':['q']},{'x':4,'q':1},600), {'a':1200.,'b':1200.,'c':600.})
 def test_cached_input_tampering_is_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'network';p.write_text('changed')
   with self.assertRaises(RuntimeError):verify_hashes({str(p):'old-hash'})
 def test_gate_rejects_missing_or_failed_route(self):
  rows=[dict(route='a',arrival=True,collision=False,teleports=0,insertion_failure=False)]*20
  self.assertFalse(gate(rows,['a','b']))
  self.assertTrue(gate(rows,['a']))
  rows=rows[:18]+[dict(route='a',arrival=False,collision=False,teleports=0,insertion_failure=False)]*2
  self.assertFalse(gate(rows,['a']))
if __name__=='__main__':unittest.main()
