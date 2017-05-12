#!/bin/bash

# for BAND in {4,3,2}; do
#   gdalwarp -t_srs EPSG:3857 LC80260382015338LGN00/LC80260382015338LGN00_B$BAND.TIF $BAND-projected.tif;
# done

# convert -combine {4,3,2}-projected.tif RGB.tif

# convert -sigmoidal-contrast 50x12% RGB.tif RGB-corrected.tif

# convert -channel B -gamma 0.925 -channel R -gamma 1.03 -channel RGB -sigmoidal-contrast 50x16% RGB.tif RGB-corrected.tif




convert -sigmoidal-contrast 50x12% /Users/cgroskopf/landsat/processed/LC80260382015338LGN00/LC80260382015338LGN00_bands_432_pan.TIF RGB-corrected.tif
