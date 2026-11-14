import tempfile,unittest,xml.etree.ElementTree as E
from pathlib import Path
from utils.extend_entry_preparation import apply_extensions,ROOT,EXTENSIONS
from utils.hv_flow_audit import sha
class EntryPreparation(unittest.TestCase):
 def test_extension_only_changes_entry_edges_and_boundary_nodes(self):
  source=ROOT/'maps/toegyewon_only/network.net.xml';source_hash=sha(source)
  with tempfile.TemporaryDirectory() as d:
   target=Path(d)/'network.net.xml';r=apply_extensions(source,target)
   self.assertEqual(sha(source),source_hash)
   self.assertEqual([x['entry'] for x in r['after'] if not x['has_fork']],['556956812#1'])
   for old,new in zip(r['before'],r['after']):self.assertAlmostEqual(new['distance']-old['distance'],EXTENSIONS.get(old['entry'],0),places=2)
   a=E.parse(source);b=E.parse(target)
   self.assertEqual([c.attrib for c in a.findall('connection')],[c.attrib for c in b.findall('connection')])
   moved={a.find(f"edge[@id='{eid}']").get('from') for eid in EXTENSIONS}
   for x,y in zip(a.getroot(),b.getroot()):
    if x.tag=='location' or (x.tag=='edge' and x.get('id') in EXTENSIONS) or (x.tag=='junction' and x.get('id') in moved):continue
    self.assertEqual(E.tostring(x),E.tostring(y))
