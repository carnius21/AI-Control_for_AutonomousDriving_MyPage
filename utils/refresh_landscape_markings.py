"""Rebuild presentation-only lane markings, preserving the source solid-line rules.
Run from repository root: python -m utils.refresh_landscape_markings
Unsurveyed boundaries retain the original default; this is not a new map survey.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from env.road_builder import marking, shifted


def main():
    folder = Path(__file__).resolve().parents[1] / 'maps' / 'toegyewon_only'
    network = ET.parse(folder / 'landscaped.net.xml')
    original = ET.parse(folder / 'network.net.xml')
    original_edges = {edge.get('id'): edge for edge in original.findall('edge') if not edge.get('function')}
    scenery = ET.parse(folder / 'scenery.add.xml')
    root = scenery.getroot()
    rules = json.loads((folder.parent / 'toegyewon_osm' / 'markings.json').read_text(encoding='utf-8'))
    edges = [edge for edge in network.findall('edge') if not edge.get('function')]
    prefixes = tuple(lane.get('id') + suffix for edge in edges for lane in edge.findall('lane') for suffix in ('_right_', '_left_'))
    for element in list(root):
        if element.get('type') == 'display' and element.get('id', '').startswith(prefixes):
            root.remove(element)
    solid_count = dashed_count = 0
    for edge in edges:
        lanes = edge.findall('lane')
        source_lanes = original_edges[edge.get('id')].findall('lane')
        assert [l.get('id') for l in lanes] == [l.get('id') for l in source_lanes]
        for index, lane in enumerate(lanes):
            points = [tuple(map(float, point.split(','))) for point in lane.get('shape').split()]
            width = float(lane.get('width', '3.2'))
            # Boundary shared with the right-hand neighbouring lane.
            solid = index == 0 or edge.get('id') in rules['solid']
            if index > 0:
                restricted = source_lanes[index].get('changeRight') or source_lanes[index-1].get('changeLeft')
                solid = solid or (restricted is not None and 'passenger' not in restricted.split() and restricted != 'all')
                solid_count += int(solid)
                dashed_count += int(not solid)
            marking(root, lane.get('id') + '_right', shifted(points, width/2-.06), dashed=not solid)
            if index == len(lanes)-1:
                marking(root, lane.get('id') + '_left', shifted(points, -width/2+.06))
    scenery.write(folder / 'scenery.add.xml', encoding='utf-8', xml_declaration=True)
    print(f'Internal boundaries: {solid_count} solid, {dashed_count} dashed; outside borders remain solid.')


if __name__ == '__main__':
    main()
