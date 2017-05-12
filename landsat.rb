require 'net/http'
require 'nokogiri'
require 'fileutils'

class Satellite
  def initialize(opts = {})
    @mission = "L"
    @sensor  = opts[:sensor]
    @version = opts[:version].to_i
  end

  def vegetation
    return %w[B6 B5 B4]    if @version < 4
    return %w[B40 B30 B20] if @version <= 5 && @sensor == "T" # 4-7 TM
    return %w[B4 B2 B1]    if @version <= 5 # 4-7 MSS
    return %w[B40 B30 B20] if @version == 7
    return %w[B5 B4 B3]
  end

  # http://landsat.usgs.gov/consumer.php
  def metadata_sensor_id
    return "LANDSAT_8"        if @version == 8
    return "LANDSAT_MSS1"     if @version < 5
    return "LANDSAT_COMBINED" if @version < 7
    return "LANDSAT_ETM"      if @version < 8 # 1999-2003 before breakage
  end

  def self.find_by_year(year)
    year = year.to_i
    return self.new({:sensor => "C", :version => "8"}) if year >= 2013
    return self.new({:sensor => "E", :version => "7"}) if year >= 1999 && year < 2003 # landsat 7 broke on may 31, 2003
    return self.new({:sensor => "T", :version => "5"}) if year >= 1984
    return self.new({:sensor => "T", :version => "4"}) if year >= 1982
    return self.new({:sensor => "M", :version => "3"}) if year >= 1978
    return self.new({:sensor => "M", :version => "2"}) if year >= 1975
    return self.new({:sensor => "M", :version => "1"})
  end
end

class Scene
  attr_reader :id, :satellite, :outdir

  def initialize(id, outdir)
    @id     = id
    @outdir = outdir
  end

  def mission
    "L"
  end

  def product
    @id[0,3]
  end

  # gs://earthengine-public/landsat/scene_list.zip
  # gs://earthengine-public/landsat/L5/
  # gs://earthengine-public/landsat/L7/
  # gs://earthengine-public/landsat/L8/
  # gs://earthengine-public/landsat/LM1/
  # gs://earthengine-public/landsat/LM2/
  # gs://earthengine-public/landsat/LM3/
  # gs://earthengine-public/landsat/LM4/
  # gs://earthengine-public/landsat/LM5/
  # gs://earthengine-public/landsat/LT4/
  # gs://earthengine-public/landsat/PE1/
  def gsproduct
    version.to_i > 4 ? "L#{version}" : "L#{sensor}#{version}"
  end

  def band_file_pattern
    id
    # return id if version.to_i < 7 || version.to_i > 7
    # return "#{mission}#{version}*_#{row}#{year}#{day}" # some odd id between L7 and path/row/day/band in L7 band files
  end

  def sensor
    @id[1]
  end

  def version
    @id[2]
  end

  def path
    @id[3,3]
  end

  def row
    @id[6,3]
  end

  def year
    @id[9,4]
  end

  def day
    @id[13,3]
  end

  def gsi
    @id[16,3]
  end

  def archive_version
    @id[19,2]
  end

  def satellite
    @satellite ||= Satellite.new({:sensor => sensor, :version => version})
  end

  def zip_exists?
    File.exists?(File.join("#{@outdir}", "#{id}.tar.bz"))
  end

  def band_files_exist?
    Dir["#{@outdir}/#{id}_B*"].length > 0
  end

  def processed_files_exist?
    Dir["#{@outdir}/#{id}*projected*"].length > 0
  end

  def download
    return if zip_exists?
    return if band_files_exist?

    puts "== downloading #{gsproduct}/#{path}/#{row}/#{id} to #{@outdir}/#{id}.tar.bz"
    `gsutil cp gs://earthengine-public/landsat/#{gsproduct}/#{path}/#{row}/#{id}.tar.bz #{@outdir}` unless File.exists?("#{@outdir}/#{id}.tar.bz")
  end

  def unzip
    `cd #{@outdir} && tar --transform 's/^.*_/#{id}_/g' -xzvf #{id}.tar.bz`
  end

  def warp(polygon_shp)
    return unless zip_exists?

    if !band_files_exist?
      unzip
    end

    if !processed_files_exist?
      satellite.vegetation.each do |band|
        # if it's landsat 8, convert to 8 bit
        if version.to_i > 7
          puts "== Landsat 8, converting to 8bit"
          `gdal_translate -of "GTiff" -co "COMPRESS=LZW" -scale 0 65535 0 255 -ot Byte #{@outdir}/#{band_file_pattern}_#{band}.TIF #{@outdir}/#{band_file_pattern}_#{band}_tmp.TIF && \
          rm #{@outdir}/#{band_file_pattern}_#{band}.TIF && mv #{@outdir}/#{band_file_pattern}_#{band}_tmp.TIF #{@outdir}/#{band_file_pattern}_#{band}.TIF`
        end
        puts "gdalwarp -t_srs \"EPSG:3857\"  #{@outdir}/#{band_file_pattern}_#{band}.TIF #{@outdir}/#{band_file_pattern}_#{band}-projected.tif"
        `gdalwarp -t_srs "EPSG:3857" -cutline #{polygon_shp} -crop_to_cutline #{@outdir}/#{band_file_pattern}_#{band}.TIF #{@outdir}/#{band_file_pattern}_#{band}-projected.tif`
      end
      puts "gdal_merge.py -separate #{@outdir}/#{band_file_pattern}_{#{satellite.vegetation.join(",")}}-projected.tif -o #{@outdir}/#{band_file_pattern}_RGB-projected.tif"
      `gdal_merge.py -separate #{@outdir}/#{band_file_pattern}_{#{satellite.vegetation.join(",")}}-projected.tif -o #{@outdir}/#{band_file_pattern}_RGB-projected.tif` #&& \
       # convert -channel B -gamma 0.925 -channel R -gamma 1.03 -channel RGB -sigmoidal-contrast 50x16% #{@outdir}/#{id}_RGB-projected.tif #{@outdir}/#{id}_RGB-projected-corrected.tif && \
       # convert -depth 8 #{@outdir}/#{id}_RGB-projected-corrected.tif  #{@outdir}/#{id}_RGB-projected-corrected-8bit.tif && \
       # listgeo -tfw #{@outdir}/#{id}_#{satellite.vegetation[0]}-projected.tif && \
       # mv #{@outdir}/#{id}_#{satellite.vegetation[0]}-projected.tfw #{@outdir}/#{id}_RGB-projected-corrected-8bit.tfw && \
       # gdal_edit.py -a_srs EPSG:3857 #{@outdir}/#{id}_RGB-projected-corrected-8bit.tif && \
       # gdal_translate -a_nodata 0 #{@outdir}/#{id}_RGB-projected-corrected-8bit.tif #{@outdir}/#{id}_RGB-projected-corrected-8bit-nodata.tif`
    end
  end

  def tfw
    `listgeo -tfw #{@outdir}/#{id}_#{satellite.vegetation[0]}-projected.tif && \
     mv #{@outdir}/#{id}_#{satellite.vegetation[0]}-projected.tfw #{@outdir}/#{id}_RGB-projected.tfw`
  end
end

class Processor
  # 6.4531
  # 3.3958
  # NWSE
  # BB = [36.42311, -115.63218, 35.90424, -114.66538]
  BB = [6.7, 3, 6.4, 3.7]

  attr_reader :year, :outdir, :satellite, :scenes

  def initialize(year, outdir)
    @year      = year
    @outdir    = File.expand_path outdir
    @satellite = Satellite.find_by_year(year)
    FileUtils.mkdir_p(outdir) unless File.directory?(outdir)
  end

  def scenes
    @scenes ||= get_scenes
  end

  def same_size
    tifs = Dir["#{@outdir}/*_RGB-projected.tif"]
    puts tifs[0]
    size = `gdalinfo #{tifs[0]}`.split("\n")[3]

    wh   = size.scan(/[\d]+/)
    puts wh
    tifs.each do |tif|
      `rm #{tif}.resized.tif`
      `gdalwarp -ts #{wh[0]} #{wh[1]} #{tif} #{tif}.resized.tif`
    end
  end

  def median
    `convert #{@outdir}/*_RGB-projected.tif -evaluate-sequence median #{@outdir}/median-out.tif`
  end

  private

  def get_scenes
    url    = "http://earthexplorer.usgs.gov/EE/InventoryStream/latlong?north=#{BB[0]}&south=#{BB[2]}4&east=#{BB[3]}8&west=#{BB[1]}&sensor=#{@satellite.metadata_sensor_id}&start_date=#{@year}-01-01&end_date=#{@year}-12-31"
    puts "trying #{url}"
    scenes = Nokogiri::XML(Net::HTTP.get(URI.parse(url))).css('metaData').select {|n| n.children.css('cloudCoverFull').text.to_i < 10 }.map {|n| n.children.css('sceneID').text }
    scenes.map!{|q| Scene.new(q, @outdir) }
    puts "== got #{scenes.length} scenes"
    scenes
  end
end

if __FILE__ == $0
  start_year = ARGV[0].to_i
  end_year   = ARGV[1].to_i
  outdir     = ARGV[2]

  if ARGV.length < 3 || ARGV.length > 3
    puts <<-EOD

      usage: ruby landsat.rb start_year end_year outdir

      example: ruby landsat.rb 1972 2014 /Volumes/Gilese581c/vegas/

      oh it wants you to have a POLYGON.shp in yr ../data/POLYGON.shp too thx
    EOD

    exit 1
  end


  puts "== doin #{start_year} up to #{end_year} in #{outdir}"
  (start_year).upto(end_year).each do |year|
    puts "== tryin #{year}"
    landsat_year = Processor.new(year, File.join(File.expand_path(outdir), year.to_s))
    scenes = landsat_year.scenes

    q = []
    scenes.map {|s| q << s }
    m = Mutex.new
    threads = (1..8).map do
      Thread.new do
        loop do
          scene = nil
          exit = false
          m.synchronize do
            if q.empty?
              exit = true
            else
              scene = q.shift
            end
          end
          Thread.exit if exit
          scene.download
          scene.warp("data/NIR-24_outline.shp")
        end
      end
    end

    threads.map(&:join)
  end
end
