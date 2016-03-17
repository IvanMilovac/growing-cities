#!/usr/bin/env python

from glob import glob
import os

from invoke import run
from invoke.exceptions import Failure

from satellite import Satellite


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
        self.scene_id = SceneID(scene_id)
        self.output_dir = output_dir

        self.satellite = Satellite(self.scene_id.version)
        self.bands = self.satellite.natural_color_bands

    @property
    def base_path(self):
        return '{output_dir}/{scene_id}'.format(
            output_dir=self.output_dir,
            scene_id=self.scene_id
        )

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
        merged_file = '%s/%s_RGB-projected.tif' % (self.output_dir, self.scene_id)

        return os.path.exists(merged_file)

    @property
    def color_corrected_file_exists(self):
        color_corrected_file = '%s/%s_RGB-projected-corrected.tif' % (self.output_dir, self.scene_id)

        return os.path.exists(color_corrected_file)

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

    def _convert_to_8bit(self, band):
        cmd = 'gdal_translate -of "GTiff" -co "COMPRESS=LZW" -scale 0 65535 0 255 -ot Byte {base_path}_{band}.TIF {base_path}_{band}_tmp.TIF'.format(
            base_path=self.base_path,
            band=band
        )

        print(cmd)
        run(cmd)

        cmd = 'rm {base_path}_{band}.TIF && mv {base_path}_{band}_tmp.TIF {base_path}_{band}.TIF'.format(
            base_path=self.base_path,
            band=band
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
                self._convert_to_8bit(band)

            base_file_path = '{base_path}_{band}'.format(
                base_path=self.base_path,
                band=band,
            )
            cmd = 'gdalwarp -t_srs "EPSG:3857" {base_file_path}.TIF {base_file_path}-projected.tif'.format(
                base_file_path=base_file_path
            )

            print(cmd)
            run(cmd)

    def merge_bands(self):
        if not self.projected_files_exist:
            raise IOError('Projected band files do not exist!')

        if self.merged_file_exists:
            return

        bands = ','.join(self.bands)

        cmd = 'gdal_merge.py -separate {base_path}_{{{bands}}}-projected.tif -o {base_path}_RGB-projected.tif'.format(
            base_path=self.base_path,
            bands=bands
        )

        print(cmd)
        run(cmd)

    def color_correct(self):
        if not self.merged_file_exists:
            raise IOError('Merged file does not exist')

        if self.color_corrected_file_exists:
            return

        # Beautiful leveling for 1985 Las Vegas
        # convert -channel R -level 8%,46% -channel G -level 11%,37% -channel B -level 28%,61% LT50390351985250XXX04_RGB-projected.tif LT50390351985250XXX04_RGB-projected-corrected.tif

        cmd = 'convert -channel R -level 8%,46% -channel G -level 11%,37% -channel B -level 28%,61% {base_path}_RGB-projected.tif {base_path}_RGB-projected-corrected.tif'.format(
            base_path=self.base_path
        )

        print(cmd)
        run(cmd)

    def process(self):
        try:
            self.download()
            self.unzip()
            self.project_bands()
            self.merge_bands()
            self.color_correct()
        except Failure as e:
            print(str(e))
