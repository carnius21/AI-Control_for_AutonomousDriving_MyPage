import unittest
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from env.navigation_observation import RouteNavigation
from env.navigation_clarity import validity_features, second_constraint_features


class ValidityTests(unittest.TestCase):
    def test_real_successive_branch_routes_have_different_future_targets(self):
        directory=Path(__file__).resolve().parents[1]/'maps/toegyewon_only'
        root=ET.parse(directory/'network.net.xml').getroot()
        edges={e.get('id'):e for e in root.findall('edge') if e.get('function')!='internal'}
        counts={e:len(x.findall('lane')) for e,x in edges.items()}
        lengths={e:float(x.find('lane').get('length')) for e,x in edges.items()}
        links=[(c.get('from'),c.get('to'),int(c.get('fromLane')),int(c.get('toLane'))) for c in root.findall('connection') if c.get('from') in edges and c.get('to') in edges]
        nav=RouteNavigation(counts,links,lengths)
        routes=json.loads((directory/'manifest.json').read_text())['routes']
        values=[]
        for name in ('route_03','route_04'):
            path=routes[name];idx=path.index('170059994')
            values.append(second_constraint_features(nav,path,idx,48))
        self.assertEqual(values[0][7],1.)
        self.assertEqual(values[1][7],1.)
        self.assertEqual(values[0][1:4],[1.,1.,-1.])
        self.assertEqual(values[1][1:4],[-1.,-1.,1.])

    def test_second_branch_is_visible_before_first(self):
        nav = RouteNavigation({'a':3,'b':3,'c':2}, [('a','b',0,0),('a','b',1,1),('b','c',1,0)], {'a':50,'b':60,'c':50})
        result = second_constraint_features(nav,['a','b','c'],0,40)
        self.assertAlmostEqual(result[0],100/300)
        self.assertEqual(result[1:7],[-1.,1.,-1.,0.,0.,0.])
        self.assertEqual(result[7],1.)

    def test_no_future_constraint_and_internal_are_explicitly_absent(self):
        nav = RouteNavigation({'a':2,'b':2}, [('a','b',0,0)], {'a':50,'b':50})
        self.assertEqual(second_constraint_features(nav,['a','b'],0,40),[-1.,0.,0.,0.,0.,0.,0.,-1.])
        self.assertEqual(second_constraint_features(nav,['a','b'],0,40,True),[-1.,0.,0.,0.,0.,0.,0.,-1.])

    def test_valid_zero_and_unknown_zero_differ(self):
        valid = dict(current_targets=[1], prepare_targets=[1])
        unknown = dict(current_targets=[], prepare_targets=[])
        self.assertEqual(RouteNavigation.offset(1, [1]), RouteNavigation.offset(1, []))
        self.assertEqual(validity_features(valid), [1., 1.])
        self.assertEqual(validity_features(unknown), [-1., -1.])

    def test_current_known_preparation_unknown(self):
        self.assertEqual(validity_features(dict(current_targets=[0, 1], prepare_targets=[])), [1., -1.])


if __name__ == '__main__':
    unittest.main()
