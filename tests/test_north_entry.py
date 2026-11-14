import tempfile,unittest
from pathlib import Path
import xml.etree.ElementTree as E
from utils.extend_north_entry import extend,ROOT
from utils.hv_flow_audit import sha
class NorthEntry(unittest.TestCase):
 def test_both_maps_keep_source_and_connections(self):
  for name in ('network.net.xml','landscaped.net.xml'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
    src=ROOT/'maps/toegyewon_only'/name;before=sha(src);dst=Path(d)/name;r=extend(src,dst)
    self.assertEqual(sha(src),before);self.assertEqual(r['lanes'],5)
    self.assertEqual(set(r['new_lengths'].values()),{583.44})
    self.assertEqual([c.attrib for c in E.parse(src).findall('connection')],[c.attrib for c in E.parse(dst).findall('connection')])
