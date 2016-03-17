#!/usr/bin/env python


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
            return ['B3', 'B2', 'B1']
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
            return ['B7', 'B5', 'B3']
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
            return ['B4', 'B3', 'B2']
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
