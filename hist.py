#!/usr/bin/env python

"""
Landsat file guide: http://landsat.usgs.gov//files_will_be_provided_with_a_Landsat_scene.php
Spectral band definitions: http://landsat.usgs.gov//band_designations_landsat_satellites.php
Band usages: http://landsat.usgs.gov//best_spectral_bands_to_use.php
"""

from glob import glob
import os

from invoke import run
from lxml import etree
from lxml.cssselect import CSSSelector
import requests

CLOUD_COVER_LIMIT = 10


class Satellite(object):
    def __init__(self, version, sensor_short, sensor_long):
        self.version = version
        self.sensor_short = sensor_short
        self.sensor_long = sensor_long

    @property
    def rgb_bands(self):
        if self.version < 4:
            # TKTK: not possible, no blue band in MSS
            return ['B6', 'B5', 'B4']
        elif self.version <= 5 and self.sensor_short == 'T':
            return ['B30', 'B20', 'B10']
        elif self.version <= 5:
            return ['B3', 'B2', 'B1']
        elif self.version == 7:
            return ['B30', 'B20', 'B10']
        else:
            return ['B4', 'B3', 'B2']

    @property
    def vegetation_bands(self):
        if self.version < 4:
            return ['B6', 'B5', 'B4']
        elif self.version <= 5 and self.sensor_short == 'T':
            return ['B40', 'B30', 'B20']
        elif self.version <= 5:
            return ['B4', 'B2', 'B1']
        elif self.version == 7:
            return ['B40', 'B30', 'B20']
        else:
            return ['B5', 'B4', 'B3']

    @property
    def google_id(self):
        if self.version > 4:
            return 'L%s' % self.version
        else:
            return 'L%s%i' % (self.sensor_short, self.version)

    @classmethod
    def for_year(cls, year):
        """
        Get the preferred satellite configuration for a given year.
        """
        if year >= 2013:
            return cls(8, 'C', 'LANDSAT_8')
        elif year >= 1999 and year < 2003:
            return cls(7, 'E', 'LANDSAT_ETM')
        elif year >= 1984:
            return cls(5, 'T', 'LANDSAT_COMBINED')
        elif year >= 1982:
            return cls(4, 'T', 'LANDSAT_MSS1')
        elif year >= 1978:
            return cls(3, 'M', 'LANDSAT_MSS1')
        elif year >= 1975:
            return cls(2, 'M', 'LANDSAT_MSS1')
        else:
            return cls(1, 'M', 'LANDSAT_MSS1')


class Scene(object):
    def __init__(self, scene_id, satellite, output_dir):
        self.scene_id = scene_id
        self.satellite = satellite
        self.output_dir = output_dir
        self.bands = self.satellite.rgb_bands

    @property
    def zip_exists(self):
        tar_path = os.path.join(self.output_dir, '%s.tar.bz' % self.scene_id)

        return os.path.exists(tar_path)

    @property
    def band_files_exist(self):
        band_files = glob('%s/%s_B*' % (self.output_dir, self.scene_id))

        return len(band_files) >= len(self.bands)

    @property
    def processed_files_exist(self):
        processed_files = glob('%s/%s*-projected.tif' % (self.output_dir, self.scene_id))

        return len(processed_files) >= len(self.bands)

    @property
    def merged_file_exists(self):
        merged_file = glob('%s/%s_RGB-projected.tif' % (self.output_dir, self.scene_id))

        return len(merged_file) > 0

    def download(self):
        if self.zip_exists:
            print('Skipping download')
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        url = 'gs://earthengine-public/landsat/{google_id}/{path}/{row}/{id}.tar.bz'.format(
            google_id=self.satellite.google_id,
            path=self.scene_id[3:6],
            row=self.scene_id[6:9],
            id=self.scene_id,
        )

        cmd = 'gsutil cp %s %s' % (url, self.output_dir)

        print(cmd)
        run(cmd)

    def unzip(self):
        if not self.zip_exists:
            raise IOError('Archive does not exist!')

        if self.band_files_exist:
            print('Skipping unzipping')
            return

        cmd = 'cd %s && tar --transform \'s/^.*_/%s_/g\' -xzvf %s.tar.bz' % (
            self.output_dir, self.scene_id, self.scene_id
        )

        print(cmd)
        run(cmd)

    def warp_bands(self):
        if not self.band_files_exist:
            raise IOError('Band files do not exist!')

        if self.processed_files_exist:
            print('Skipping warping')
            return

        for band in self.bands:
            if self.satellite.version > 7:
                # TKTK: Convert to 8 bit
                pass

            base_path = '{output_dir}/{scene_id}_{band}'.format(
                output_dir=self.output_dir,
                scene_id=self.scene_id,
                band=band,
            )
            cmd = 'gdalwarp -t_srs "EPSG:3857" {base_path}.TIF {base_path}-projected.tif'.format(
                base_path=base_path
            )

            print(cmd)
            run(cmd)

    def merge_bands(self):
        if not self.processed_files_exist:
            raise IOError('Processed band files do not exist!')

        if self.merged_file_exists:
            print('Skipping merging')
            return

        base_path = '{output_dir}/{scene_id}'.format(
            output_dir=self.output_dir,
            scene_id=self.scene_id
        )
        bands = ','.join(self.bands)

        cmd = 'gdal_merge.py -separate {base_path}_{{{bands}}}-projected.tif -o {base_path}_RGB-projected.tif'.format(
            base_path=base_path,
            bands=bands
        )

        print(cmd)
        run(cmd)


def cssselect(el, css):
    selector = CSSSelector('ns|%s' % css, namespaces={ 'ns': 'http://upe.ldcm.usgs.gov/schema/metadata' })
    return selector(el)

def cloud_filter(metadata):
    cloud_cover_el = cssselect(metadata, 'cloudCoverFull')[0]

    value = float(cloud_cover_el.text)

    if value > CLOUD_COVER_LIMIT:
        print('Skipping %.0f%% cloud cover' % value)
        return False

    return True

def get_scene_id(metadata):
    scene_id_el = cssselect(metadata, 'sceneID')[0]

    return scene_id_el.text

def get_scenes(satellite, year, bb):
    url = 'http://earthexplorer.usgs.gov/EE/InventoryStream/latlong?north={bb[0]}&south={bb[2]}&east={bb[3]}&west={bb[1]}&sensor={sensor}&start_date={year}-01-01&end_date={year}-12-31'.format(
        bb=bb,
        sensor=satellite.sensor_long,
        year=year
    )
    print(url)

    r = requests.get(url)
    content = r.content
    xml = etree.fromstring(content)
    metadata = cssselect(xml, 'metaData')
    cloudless = filter(cloud_filter, metadata)
    scene_ids = map(get_scene_id, cloudless)

    return scene_ids

def main():
    bounding_box = [6.7, 3, 6.4, 3.7]

    start_year = 1985
    end_year = 1990

    output_dir = 'data'

    for year in range(start_year, end_year + 1):
        print(year)
        year_dir = os.path.join(output_dir, str(year))

        satellite = Satellite.for_year(year)
        scene_ids = get_scenes(satellite, year, bounding_box)

        if scene_ids:
            print('Found %i scenes' % len(scene_ids))
        else:
            print('No scenes found')

        for scene_id in scene_ids:
            scene = Scene(scene_id, satellite, year_dir)

            scene.download()
            scene.unzip()
            scene.warp_bands()
            scene.merge_bands()


if __name__ == '__main__':
    main()
