growing-cities
==============

Based on Ruby code written by ProPublica for their [Las Vegas Growth Map](https://projects.propublica.org/las-vegas-growth-map/).

Setup
-----

Requires Python 2.7 and GDAL.

```
mkvirtualenv growing-cities
pip install requests lxml cssselect invoke pyyaml rasterio

gem install net
gem install nokogiri
gem install fileutils

# Install GDAL with Python support
brew install gdal --with-python --with-python3 --with-postgresql

# Hotlink GDAL python modules into virtualenv
echo 'import site; site.addsitedir("/usr/local/lib/python2.7/site-packages")' >> /Users/cgroskopf/.virtualenvs/growing-cities/lib/python2.7/site-packages/homebrew.pth

# Install Google Cloud utils for downloading files
pip install gsutil

# Install linux tar utility
brew install gnu-tar --with-default-names

mkdir data

python main.py tyler.yml
```

TODO
----

* Purge cloud cover
* Balance colors
* Pansharpen Landsat 8 images
