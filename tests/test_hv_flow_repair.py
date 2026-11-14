import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from utils.hv_flow_repair import SOURCE_NETWORK, preserve_geometry_zipper, validate_geometry


class GeometryPreservation(unittest.TestCase):
    def test_zipper_keeps_every_lane_and_connection(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            target = folder/'patched.net.xml'
            preserve_geometry_zipper(SOURCE_NETWORK, target, folder)
            report = validate_geometry(SOURCE_NETWORK, target)
            self.assertEqual(report['weave_length'], '51.07')
            self.assertEqual(report['speed_changed_lanes'], [])
            # The old implementation replaced the whole network: this must fail.
            with self.assertRaises(AssertionError):
                validate_geometry(SOURCE_NETWORK, folder/'generated.net.xml')

    def test_speed_exception_cannot_hide_length_or_connectivity_changes(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)/'changed.net.xml'
            tree = ET.parse(SOURCE_NETWORK)
            lane = tree.find("edge[@id='170059994']/lane")
            lane.set('speed', '11.11')
            tree.write(target)
            validate_geometry(SOURCE_NETWORK, target, ('170059994',))
            lane.set('length', '29.32')
            tree.write(target)
            with self.assertRaises(AssertionError):
                validate_geometry(SOURCE_NETWORK, target, ('170059994',))


if __name__ == '__main__':
    unittest.main()
