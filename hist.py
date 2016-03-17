#!/usr/bin/env python

"""
Landsat file guide: http://landsat.usgs.gov//files_will_be_provided_with_a_Landsat_scene.php
Spectral band definitions: http://landsat.usgs.gov//band_designations_landsat_satellites.php
Band usages: http://landsat.usgs.gov//best_spectral_bands_to_use.php
"""

from glob import glob
import os
import sys

from invoke import run
from lxml import etree
from lxml.cssselect import CSSSelector
import requests

CLOUD_COVER_LIMIT = 10


class Satellite(object):
    """
    Configuration data for a given Landsat satellite.
    """
    def __init__(self, version):
        if version == 6:
            raise ValueError('There is no Landsat 6 data due to a rocket failure.')
        elif version > 8:
            raise ValueError('Landsat 8 is the highest active version.')

        self.version = version

    @property
    def sensor(self):
        if self.version == 8:
            return 'C'
        elif self.version == 7:
            return 'E'
        elif self.version >= 4:
            return 'T'
        else:
            return 'M'

    @property
    def natural_color_bands(self):
        """
        4-3-2 natural color.
        """
        if self.version < 4:
            raise ValueError('True color is not possible for Landsats 1-3 as they did not have a blue band.')
        elif self.version <= 5 and self.sensor == 'T':
            return ['B30', 'B20', 'B10']
        elif self.version <= 5:
            return ['B3', 'B2', 'B1']
        elif self.version == 7:
            return ['B30', 'B20', 'B10']
        else:
            return ['B4', 'B3', 'B2']

    @property
    def urban_false_color_bands(self):
        """
        7-6-4 false color for analyzing urban areas.

        http://www.exelisvis.com/Home/NewsUpdates/TabId/170/ArtMID/735/ArticleID/14305/The-Many-Band-Combinations-of-Landsat-8.aspx
        """
        if self.version < 4:
            raise ValueError('Urban false color is not possible for Landsats 1-3 as they did not have short-wave infrared bands.')
        elif self.version <= 5 and self.sensor == 'T':
            return ['B70', 'B50', 'B30']
        elif self.version <= 5:
            return ['B7', 'B5', 'B3']
        elif self.version == 7:
            return ['B70', 'B50', 'B30']
        else:
            return ['B7', 'B6', 'B4']

    @property
    def vegetation_false_color_bands(self):
        """
        5-4-3 color infrared for analyzing vegetation.

        http://www.exelisvis.com/Home/NewsUpdates/TabId/170/ArtMID/735/ArticleID/14305/The-Many-Band-Combinations-of-Landsat-8.aspx
        """
        if self.version < 4:
            return ['B6', 'B5', 'B4']
        elif self.version <= 5 and self.sensor == 'T':
            return ['B40', 'B30', 'B20']
        elif self.version <= 5:
            return ['B4', 'B2', 'B1']
        elif self.version == 7:
            return ['B40', 'B30', 'B20']
        else:
            return ['B5', 'B4', 'B3']

    @classmethod
    def for_year(cls, year):
        """
        Get the preferred satellite configuration for a given year.
        """
        if year >= 2013:
            return cls(8)
        elif year >= 1999 and year < 2003:
            return cls(7)
        elif year >= 1984:
            return cls(5)
        elif year >= 1982:
            return cls(4)
        elif year >= 1978:
            return cls(3)
        elif year >= 1975:
            return cls(2)
        else:
            return cls(1)


class SceneID(str):
    """
    A Landsat scene identifier like: LT41910561988052AAA03.

    Naming convention is defined at:
    http://landsat.usgs.gov/naming_conventions_scene_identifiers.php
    """
    @property
    def sensor(self):
        return self[1]

    @property
    def version(self):
        return int(self[2])

    @property
    def path(self):
        return self[3:6]

    @property
    def row(self):
        return self[6:9]

    @property
    def year(self):
        return self[9:13]

    @property
    def day(self):
        return self[13:16]

    @property
    def ground_station_id(self):
        return self[16:19]

    @property
    def archive_version(self):
        return self[19:21]

    @property
    def google_id(self):
        if self.version > 4:
            return 'L%s' % self.version
        else:
            return 'L%s%i' % (self.sensor, self.version)


class Scene(object):
    """
    Encasulates the processing for a single scene.
    """
    def __init__(self, scene_id, output_dir):
        self.scene_id = scene_id
        self.output_dir = output_dir

        self.satellite = Satellite(self.scene_id.version)
        self.bands = self.satellite.urban_false_color_bands

    @property
    def zip_exists(self):
        tar_path = os.path.join(self.output_dir, '%s.tar.bz' % self.scene_id)

        return os.path.exists(tar_path)

    @property
    def band_files_exist(self):
        band_files = glob('%s/%s_B*' % (self.output_dir, self.scene_id))

        return len(band_files) >= len(self.bands)

    @property
    def projected_files_exist(self):
        projected_files = glob('%s/%s*-projected.tif' % (self.output_dir, self.scene_id))

        return len(projected_files) >= len(self.bands)

    @property
    def merged_file_exists(self):
        merged_file = glob('%s/%s_RGB-projected.tif' % (self.output_dir, self.scene_id))

        return len(merged_file) > 0

    def download(self):
        """
        Download this landsat scene.
        """
        if self.zip_exists:
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        url = 'gs://earthengine-public/landsat/{id.google_id}/{id.path}/{id.row}/{id}.tar.bz'.format(id=self.scene_id)

        cmd = 'gsutil cp %s %s' % (url, self.output_dir)

        print(cmd)
        run(cmd)

    def unzip(self):
        """
        Unzip this landsat scene after download.
        """
        if not self.zip_exists:
            raise IOError('Archive does not exist!')

        if self.band_files_exist:
            return

        cmd = 'cd %s && tar --transform \'s/^.*_/%s_/g\' -xzvf %s.tar.bz' % (
            self.output_dir, self.scene_id, self.scene_id
        )

        print(cmd)
        run(cmd)

    def project_bands(self):
        if not self.band_files_exist:
            raise IOError('Band files do not exist!')

        if self.projected_files_exist:
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
        if not self.projected_files_exist:
            raise IOError('Projected band files do not exist!')

        if self.merged_file_exists:
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


class EarthExplorer(object):
    """
    Search USGS EarthExplorer for scene identifiers.
    """
    def __init__(self, year, bounding_box):
        self.year = year
        self.bounding_box = bounding_box

    def _get_dataset_name(self):
        """
        Get the correct EarthExplorer dataset name for the given year.
        """
        # Landsat 8
        if self.year >= 2013:
            return 'LANDSAT_8'
        # Landsat 1-4
        elif self.year < 1984:
            return 'LANDSAT_MSS1'
        # Landsat 5
        elif self.year < 1999:
            return 'LANDSAT_COMBINED'
        # Landsat 7
        else:
            return 'LANDSAT_ETM'

    def get_scenes(self):
        """
        Fetch a scene list from the EarthExplorer API. Individual scenes are
        parsed and returned as :class:`.SceneID` instances.
        """
        url = 'http://earthexplorer.usgs.gov/EE/InventoryStream/latlong?north={bb[0]}&south={bb[2]}&east={bb[3]}&west={bb[1]}&sensor={sensor}&start_date={year}-01-01&end_date={year}-12-31'.format(
            bb=self.bounding_box,
            sensor=self._get_dataset_name(),
            year=self.year
        )
        print(url)

        r = requests.get(url)
        content = r.content
        xml = etree.fromstring(content)

        def cssselect(el, css):
            selector = CSSSelector('ns|%s' % css, namespaces={ 'ns': 'http://upe.ldcm.usgs.gov/schema/metadata' })

            return selector(el)

        def cloud_filter(metadata):
            scene_id = cssselect(metadata, 'sceneID')[0].text
            cloud_cover_el = cssselect(metadata, 'cloudCoverFull')[0]

            value = float(cloud_cover_el.text)

            if value > CLOUD_COVER_LIMIT:
                print('Skipping %s, %.0f%% cloud cover' % (scene_id, value))
                return False

            return True

        def get_scene_id(metadata):
            scene_id_el = cssselect(metadata, 'sceneID')[0]

            return SceneID(scene_id_el.text)

        metadata = cssselect(xml, 'metaData')
        cloudless = filter(cloud_filter, metadata)
        scene_ids = map(get_scene_id, cloudless)

        return scene_ids

def main():
    bounding_box = [6.7, 3, 6.4, 3.7]

    start_year = int(sys.argv[1])
    end_year = int(sys.argv[2])

    output_dir = 'data'

    for year in range(start_year, end_year + 1):
        print(year)
        year_dir = os.path.join(output_dir, str(year))

        explorer = EarthExplorer(year, bounding_box)
        scene_ids = explorer.get_scenes()

        for scene_id in scene_ids:
            print('Processing %s' % scene_id)
            scene = Scene(scene_id, year_dir)

            scene.download()
            scene.unzip()
            scene.project_bands()
            scene.merge_bands()


if __name__ == '__main__':
    main()
