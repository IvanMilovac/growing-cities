#!/usr/bin/env python

"""
Landsat file guide: http://landsat.usgs.gov//files_will_be_provided_with_a_Landsat_scene.php
Spectral band definitions: http://landsat.usgs.gov//band_designations_landsat_satellites.php
Band usages: http://landsat.usgs.gov//best_spectral_bands_to_use.php
"""

from glob import glob
import os
import sys
import yaml

import rasterio
from rasterio.tools.merge import merge

from earthexplorer import EarthExplorer
from scene import Scene


def merge_adjacent(path_dir):
    output_path = '%s/merged.tif' % path_dir

    with rasterio.drivers():
        files = glob('%s/**/**/crop.tif' % path_dir)

        print(files)

        sources = [rasterio.open(f) for f in files]
        dest, output_transform = merge(sources)

        profile = sources[0].profile
        profile.pop('affine')
        profile['transform'] = output_transform
        profile['height'] = dest.shape[1]
        profile['width'] = dest.shape[2]
        profile['driver'] = 'GTiff'

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(dest)


def main():
    output_dir = 'data'

    with open(sys.argv[1]) as f:
        config = yaml.load(f)

    for year in range(config['start_year'], config['end_year'] + 1):
        print(year)
        year_dir = os.path.join(output_dir, str(year))

        for path in range(config['path_start'], config['path_end'] + 1):
            path_dir = os.path.join(year_dir, str(path))
            print(path)

            for row in range(config['row_start'], config['row_end'] + 1):
                row_dir = os.path.join(path_dir, str(row))
                print(row)

                explorer = EarthExplorer(year, path, row, max_cloud_cover=config['max_cloud_cover'])
                scene_ids = explorer.get_scenes()

                for scene_id in scene_ids[:1]:
                    print('Processing %s' % scene_id)

                    scene_dir = os.path.join(row_dir, scene_id)
                    scene = Scene(scene_id, scene_dir, config['levels'], config['cutline'])
                    scene.process()

            merge_adjacent(path_dir)


if __name__ == '__main__':
    main()
