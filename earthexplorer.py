#!/usr/bin/env python

from lxml import etree
from lxml.cssselect import CSSSelector
import requests


class EarthExplorer(object):
    """
    Search USGS EarthExplorer for scene identifiers.
    """
    def __init__(self, year, path, row, max_cloud_cover=0):
        self.year = year
        self.path = path
        self.row = row
        self.max_cloud_cover = max_cloud_cover

    def _get_dataset_name(self):
        """
        Get the correct EarthExplorer dataset name for the given year.
        """
        # Landsat 8
        if self.year >= 2013:
            return 'LANDSAT_8'
        # Landsat 5 for broken years of Landsat 7
        elif self.year >= 2003:
            return 'LANDSAT_COMBINED'
        # Landsat 7
        elif self.year >= 1999:
            return 'LANDSAT_ETM'
        # Landsat 5
        elif self.year >= 1984:
            return 'LANDSAT_COMBINED'
        # Landsat 1-4
        elif self.year >= 1972:
            return 'LANDSAT_MSS1'
        else:
            raise ValueError('Landsat 1 did not come online until 1972.')

    def get_scenes(self):
        """
        Fetch a scene list from the EarthExplorer API. Individual scenes are
        parsed and returned as :class:`.SceneID` instances.
        """
        url = 'http://earthexplorer.usgs.gov/EE/InventoryStream/pathrow?start_path={path}&end_path={path}&start_row={row}&end_row={row}&sensor={sensor}&start_date={year}-01-01&end_date={year}-12-31'.format(
            path=self.path,
            row=self.row,
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

            if value > self.max_cloud_cover:
                print('Skipping %s, %.0f%% cloud cover' % (scene_id, value))
                return False

            return True

        def get_scene_id(metadata):
            scene_id_el = cssselect(metadata, 'sceneID')[0]

            return scene_id_el.text

        metadata = cssselect(xml, 'metaData')
        cloudless = filter(cloud_filter, metadata)
        scene_ids = map(get_scene_id, cloudless)

        return scene_ids
