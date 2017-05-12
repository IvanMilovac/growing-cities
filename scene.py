#!/usr/bin/env python

from glob import glob
import os

from invoke import run
from invoke.exceptions import Failure
import numpy as np
import rasterio
from skimage import exposure, img_as_ubyte

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
    def __init__(self, scene_id, output_dir, levels, cutline):
        self.scene_id = SceneID(scene_id)
        self.output_dir = output_dir
        self.levels = levels
        self.cutline = cutline

        self.satellite = Satellite(self.scene_id.version)

    @property
    def bands(self):
        long_name = '{base_path}_B10.TIF'.format(base_path=self.base_path)

        if os.path.exists(long_name):
            return ['B%i0' % b for b in self.satellite.natural_color_bands]
        else:
            return ['B%i' % b for b in self.satellite.natural_color_bands]

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
        band_files = glob('%s/*_B*' % self.output_dir)

        return len(band_files) >= len(self.bands)

    @property
    def projected_files_exist(self):
        projected_files = glob('%s/*-projected.tif' % self.output_dir)

        return len(projected_files) >= len(self.bands)

    @property
    def merged_file_exists(self):
        merged_file = '%s/merged.tif' % self.output_dir

        return os.path.exists(merged_file)

    @property
    def color_corrected_file_exists(self):
        color_corrected_file = '%s/color_corrected.tif' % self.output_dir

        return os.path.exists(color_corrected_file)

    @property
    def crop_file_exists(self):
        crop_file = '%s/crop.tif' % self.output_dir

        return os.path.exists(crop_file)

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
                base_file_path=base_file_path,
                cutline=self.cutline
            )

            print(cmd)
            run(cmd)

    def merge_bands(self):
        if not self.projected_files_exist:
            raise IOError('Projected band files do not exist!')

        if self.merged_file_exists:
            return

        bands = ','.join(self.bands)

        cmd = 'rio stack {base_path}_{{{bands}}}-projected.tif -o {output_dir}/merged.tif'.format(
            base_path=self.base_path,
            bands=bands,
            output_dir=self.output_dir
        )

        print(cmd)
        run(cmd)

    def crop(self):
        if not self.merged_file_exists:
            raise IOError('Merged file does not exist')

        if self.crop_file_exists:
            return

        cmd = 'gdalwarp -cutline {cutline} -crop_to_cutline {output_dir}/merged.tif {output_dir}/crop.tif'.format(
            cutline=self.cutline,
            output_dir=self.output_dir
        )

        print(cmd)
        run(cmd)

    def hist_match(self, source, template):
        """
        Adjust the pixel values of a grayscale image such that its histogram
        matches that of a target image

        Arguments:
        -----------
            source: np.ndarray
                Image to transform; the histogram is computed over the flattened
                array
            template: np.ndarray
                Template image; can have different dimensions to source
        Returns:
        -----------
            matched: np.ndarray
                The transformed output image
        """

        oldshape = source.shape
        source = source.ravel()
        template = template.ravel()

        # get the set of unique pixel values and their corresponding indices and
        # counts
        s_values, bin_idx, s_counts = np.unique(source, return_inverse=True,
                                                return_counts=True)
        t_values, t_counts = np.unique(template, return_counts=True)

        s_counts[0] = 0
        print(t_counts)

        # take the cumsum of the counts and normalize by the number of pixels to
        # get the empirical cumulative distribution functions for the source and
        # template images (maps pixel value --> quantile)
        s_quantiles = np.cumsum(s_counts)
        s_quantiles = (255 * s_quantiles / s_quantiles[-1]).astype(np.ubyte) #normalize
        t_quantiles = np.cumsum(t_counts).astype(np.float64)
        t_quantiles = (255 * t_quantiles / t_quantiles[-1]).astype(np.ubyte) #normalize

        # source_cdf, source_bin_centers = exposure.cumulative_distribution(source)
        # template_cdf, template_bin_centers = exposure.cumulative_distribution(template)
        # out = np.interp(image.flat, bin_centers, cdf)
        # out = np.interp(source.flat, template_bin_centers, template_cdf)

        # # interpolate linearly to find the pixel values in the template image
        # # that correspond most closely to the quantiles in the source image
        interp_t_values = np.interp(s_quantiles, t_quantiles, t_values).astype(np.ubyte)

        print interp_t_values

        return interp_t_values[bin_idx].reshape(oldshape)

        # return out.reshape(oldshape)

    def color_correct(self):
        if not self.crop_file_exists:
            raise IOError('Crop file does not exist')

        if self.color_corrected_file_exists:
            return

        print('Equalizing histograms')

        with rasterio.drivers():
            with rasterio.open('correct.tif') as f:
                template = np.rollaxis(np.rollaxis(f.read(), 1), 2, 1)

            with rasterio.open('%s/crop.tif' % self.output_dir) as f:
                data = f.read()
                profile = f.profile

            rolled = np.rollaxis(np.rollaxis(data, 1), 2, 1)

            # new_bands = []
            #
            # for b, band in enumerate(rolled.T):
            #     # R
            #     if b == 0:
            #         in_range = (28, 130)
            #     # G
            #     elif b == 1:
            #         in_range = (41, 105)
            #     # B
            #     elif b == 2:
            #         in_range = (58, 120)
            #
            #     new_bands.append(
            #         exposure.rescale_intensity(band, in_range=in_range)
            #     )
            #
            # rescaled = np.array(new_bands).T

            # rescaled = img_as_ubyte(self.hist_match(rolled, template))

            # rolled = exposure.adjust_gamma(rolled, 1.25)
            rescaled = exposure.rescale_intensity(rolled, in_range=(1, 255))
            rescaled = img_as_ubyte(exposure.equalize_adapthist(rolled))
            # rescaled = correct(rolled)
            # rescaled = img_as_ubyte(exposure.adjust_sigmoid(rolled, 0.25, 10))

            unrolled = np.rollaxis(rescaled, 2)

            with rasterio.open('%s/color_corrected.tif' % self.output_dir, 'w', **profile) as f:
                f.write(unrolled)

    def process(self):
        print('{s.year} {s.day} {s.path} {s.row}'.format(s=self.scene_id))

        try:
            self.download()
            self.unzip()
            self.project_bands()
            self.merge_bands()
            self.crop()
            self.color_correct()
        except Failure as e:
            print(str(e))
