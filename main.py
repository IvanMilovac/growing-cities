#!/usr/bin/env python

"""
Landsat file guide: http://landsat.usgs.gov//files_will_be_provided_with_a_Landsat_scene.php
Spectral band definitions: http://landsat.usgs.gov//band_designations_landsat_satellites.php
Band usages: http://landsat.usgs.gov//best_spectral_bands_to_use.php
"""

import os
import sys

from earthexplorer import EarthExplorer
from scene import Scene


def main():
    # NWSE
    # Lagos
    # bounding_box = [6.7, 3, 6.4, 3.7]

    # Hong Kong
    # bounding_box = [22.6, 113.7, 22.1, 114.5]

    # Vegas
    # bounding_box = [36.42311, -115.63218, 35.90424, -114.66538]

    # Kangbashi New Area
    # 39.603704, 109.782772
    bounding_box = [39.6, 109.6, 39.5, 110]

    start_year = int(sys.argv[1])
    end_year = int(sys.argv[2])

    output_dir = 'data'

    for year in range(start_year, end_year + 1):
        print(year)
        year_dir = os.path.join(output_dir, str(year))

        explorer = EarthExplorer(year, bounding_box)
        scene_ids = explorer.get_scenes()

        for scene_id in scene_ids[:1]:
            print('Processing %s' % scene_id)

            scene_dir = os.path.join(year_dir, scene_id)
            scene = Scene(scene_id, scene_dir)
            scene.process()


if __name__ == '__main__':
    main()
