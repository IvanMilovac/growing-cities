#!/usr/bin/env python

"""
Landsat file guide: http://landsat.usgs.gov//files_will_be_provided_with_a_Landsat_scene.php
Spectral band definitions: http://landsat.usgs.gov//band_designations_landsat_satellites.php
Band usages: http://landsat.usgs.gov//best_spectral_bands_to_use.php
"""

import yaml
import os
import sys

from earthexplorer import EarthExplorer
from scene import Scene


def main():
    output_dir = 'data'

    with open(sys.argv[1]) as f:
        config = yaml.load(f)

    bounding_box = [
        config['north'],
        config['west'],
        config['south'],
        config['east']
    ]

    for year in range(config['start_year'], config['end_year'] + 1):
        print(year)
        year_dir = os.path.join(output_dir, str(year))

        explorer = EarthExplorer(year, bounding_box, max_cloud_cover=config['max_cloud_cover'])
        scene_ids = explorer.get_scenes()

        for scene_id in scene_ids[:1]:
            print('Processing %s' % scene_id)

            scene_dir = os.path.join(year_dir, scene_id)
            scene = Scene(scene_id, scene_dir)
            scene.process()


if __name__ == '__main__':
    main()
