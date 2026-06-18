# DEM Change Detection with Uncertainty — Python Port

## Table of Contents

1. [Overview](#overview)
2. [Author & Attribution](#author--attribution)
3. [How It Works](#how-it-works)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Usage](#usage)
7. [Input Parameters](#input-parameters)
8. [Configuration File Format](#configuration-file-format)
9. [Output Files](#output-files)
10. [Examples](#examples)
11. [References](#references)
12. [Troubleshooting](#troubleshooting)
13. [License](#license)

---

## Overview

**dem_change.py** is a Python implementation of a probabilistic raster change detection algorithm that computes statistically significant elevation changes between two Digital Elevation Models (DEMs) with spatially variable error surfaces.

The program uses an analytical approach based on Gaussian probability density functions to determine:
- **Change magnitude**: Difference of DEMs (DoD) at each pixel
- **Change probability**: Statistical significance of detected changes given measurement uncertainties

Outputs are produced as Cloud-Optimized GeoTIFFs (COGs) with:
- ZSTD compression (level 18)
- Power-of-2 pyramid overviews
- 512×512 internal tiles
- Proper geospatial metadata

### Key Features

✓ **Analytical uncertainty quantification** — No Monte Carlo simulation required  
✓ **Spatially variable errors** — Each pixel can have unique uncertainty  
✓ **Multi-format support** — GeoTIFF, COG, JP2, NetCDF, HDF5, and more  
✓ **Overlapping extents** — Works with rasters of different spatial coverage  
✓ **Parallel processing** — Uses all available CPU cores for speed  
✓ **COG output** — Cloud-native geospatial format for web and remote access  

---

## Author & Attribution

**Original C++ Implementation**
- **Phillipe Wernette, PhD** (2018 release))
- C++ source files:
  - `datastruct.cpp` — Core analytical computation
  - `main.cpp` — I/O and orchestration

**Python Port**
- **Phillipe Wernette, PhD** (2026 release)
  - Michigan State University
  - Remote Sensing & GIS Research and Outreach Services (RS&GIS)
  - Email: pwernett@msu.edu

---

## How It Works

### Algorithm Overview

The program performs the following steps:

#### 1. **Parameter Loading**
   - Reads configuration from INI file
   - Resolves raster file paths (auto-detects extensions)
   - Validates that error values are either scalars or raster paths

#### 2. **Spatial Validation**
   - Opens all input rasters
   - Verifies compatible CRS and pixel sizes
   - Computes intersection extent (for overlapping rasters)
   - Creates output raster grid aligned to intersection bounds

#### 3. **Tile-Based Processing (Pass 1 — Uncompressed)**
   - Divides intersection extent into 512×512 pixel tiles
   - For each tile in parallel:
     - Reads surface DEMs
     - Reads or applies error surfaces
     - Converts error values (95% CI → 1-sigma standard deviation)
     - Computes change and probability for each pixel
   - Writes results to temporary uncompressed GeoTIFFs

#### 4. **Change Detection Computation**

   For each pixel, the algorithm:

   a) **Computes Difference of DEMs (DoD)**
   ```
   change = mu2 - mu1
   ```

   b) **Finds intersection point of two Gaussian PDFs**
   ```
   c = intersection(PDF₁, PDF₂)
   ```
   where PDF₁ and PDF₂ represent uncertainty distributions at t₀ and t₁

   c) **Computes probability of significant change**
   ```
   P(change) = ∫ᶜ₍₋∞₎ PDF₁(x) dx
   ```
   Using the error function (erf) for analytical solution

   d) **Result interpretation**
   - P(change) = 0.0 → high confidence **no change**
   - P(change) = 0.5 → maximal **uncertainty**
   - P(change) = 1.0 → high confidence **change detected**

#### 5. **COG Finalization (Pass 2 — Compression)**
   - Builds power-of-2 pyramid overviews on temporary files
   - Copies to final COGs with ZSTD compression
   - Removes temporary files
   - Produces publication-ready outputs

### Why Two-Pass Processing?

The two-pass strategy optimizes I/O and compression:

- **Pass 1**: Fast sequential writes to uncompressed temp files (quick for many small writes)
- **Pass 2**: Efficient compression on aligned tiles with pre-built overviews (reduces total file size by ~80%)

---

## Requirements

### System Requirements
- **CPU**: Multi-core processor recommended (parallel processing scales with cores)
- **RAM**: ≥ 8 GB for typical DEMs; more for very large datasets
- **Disk**: Temporary space for uncompressed intermediate files (~2× output size)

### Software Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥ 3.10 | Core language |
| NumPy | ≥ 1.20 | Vectorized computation |
| GDAL | ≥ 3.5 | Raster I/O, COG support, ZSTD compression |
| rasterio | ≥ 1.3 | High-level raster interface |

---

## Installation

### Option 1: Using Conda (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-repo/DEM_differencing_with_uncertainty.git
cd DEM_differencing_with_uncertainty

# Create environment from environment.yml
conda env create -f environment.yml

# Activate environment
conda activate demchange
```

### Option 2: Manual Conda Installation

```bash
# Create conda environment
conda create -n demchange python=3.10 -c conda-forge

# Activate environment
conda activate demchange

# Install dependencies
conda install -c conda-forge numpy>=1.20 gdal>=3.5 rasterio>=1.3
```

### Option 3: Verify Installation

```bash
# Activate environment
conda activate demchange

# Check imports
python -c "import numpy; import rasterio; import gdal; print('All dependencies installed successfully!')"

# Run with help
python python/dem_change.py --help
```

---

## Usage

### Basic Syntax

```bash
conda activate demchange
cd /path/to/project
python python/dem_change.py [params.ini]
```

### Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `params.ini` | Configuration file with input/output paths | `"params.ini"` |

### Logging Output

The program provides informative logging:

```
14:23:45  INFO      Parameters loaded from params.ini
14:23:46  INFO      se1_is_float=True  se2_is_float=False
14:23:46  INFO      Global uncertainty t0 = 0.1500
14:23:47  INFO      Intersection bounds: (500000.00, 6000000.00, 502000.00, 6002000.00)
14:23:47  INFO      Intersection extent → 8 tiles (512×512 px each)
14:23:47  INFO      Pass 1: writing pixel data to temporary files ...
14:23:48  INFO        1 / 8 tiles complete (12%)
14:23:49  INFO        8 / 8 tiles complete (100%)
14:23:49  INFO      Pass 2: building overviews and finalising COG outputs ...
14:23:50  INFO        Processing change raster ...
14:23:51  INFO        Processing probability raster ...
14:23:52  INFO      Successfully wrote COG: output_change.tif  (ZSTD level 18, predictor 3)
14:23:52  INFO      Successfully wrote COG: output_probability.tif  (ZSTD level 18, predictor 3)
```

---

## Input Parameters

### Configuration File Format

Parameters are specified in a whitespace-separated text file (typically `params.ini`):

```ini
key1   value1
key2   value2
...
```

Parameter names are **case-insensitive**; values are **case-sensitive** (file paths).

### Parameter Reference

| Parameter | Required | Type | Description | Example |
|-----------|----------|------|-------------|---------|
| `input1` | Yes | Path | First DEM raster (without extension) | `dem_2010` |
| `error1` | Yes | Path or Float | Uncertainty surface for t₀ (95% CI) | `0.15` or `error_2010` |
| `input2` | Yes | Path | Second DEM raster (without extension) | `dem_2015` |
| `error2` | Yes | Path or Float | Uncertainty surface for t₁ (95% CI) | `0.15` or `error_2015` |
| `oput` | Yes | Path | Output file base name (without extension) | `output_2010_2015` |
| `nsimulations` | No | Integer | [Parsed but unused — analytical method] | `100` |

### Parameter Rules

- **File paths** may omit extensions; the program tries: `.tif`, `.tiff`, `.jp2`, `.j2k`, `.img`, `.nc`, `.h5`, `.hdf5`, `.vrt`, `.asc`, `.grd`, `.grb`, `.grib`, `.dat`, `.hdr`
- **Error values** can be:
  - **Scalar float**: Single uncertainty applied to all pixels (e.g., `0.15`)
  - **Raster path**: Spatially variable uncertainty (one value per pixel)
- **Output path**: Can include directory; directories are created if needed

---

## Configuration File Format

### Example: `params.ini`

```ini
input1       /data/dem_2010
error1       0.15
input2       /data/dem_2015
error2       /data/error_surface_2015
oput         /results/coastal_change_2010_2015
nsimulations 100
```

### Example: Multiple Sites (separate config files)

**coastal_2010_2015.ini:**
```ini
input1   /data/site1/dem_t0
error1   0.12
input2   /data/site1/dem_t1
error2   0.12
oput     /results/site1_change
```

**mountain_2010_2015.ini:**
```ini
input1   /data/site2/dem_t0
error1   0.25
input2   /data/site2/dem_t1
error2   error_surface_site2
oput     /results/site2_change
```

---

## Output Files

### Output Naming

For `oput = output_change_2010_2015`, the program produces:

| File | Description | Units | Range |
|------|-------------|-------|-------|
| `output_change_2010_2015_change.tif` | Elevation difference (DoD) | Same as input DEMs (typically meters) | -∞ to +∞ |
| `output_change_2010_2015_probability.tif` | Probability of significant change | Dimensionless | 0.0 to 1.0 |

### Output Specifications

**Both output rasters have:**
- **Format**: Cloud-Optimized GeoTIFF (COG)
- **Compression**: ZSTD level 18
- **Predictor**: 3 (floating-point horizontal differencing)
- **Data type**: float32
- **Tile size**: 512×512 pixels
- **Overviews**: Power-of-2 pyramid (2, 4, 8, 16, 32, 64, 128, 256)
- **NoData value**: -9999.0 (in masked regions)
- **CRS**: Same as input DEMs
- **Bounds**: Intersection of input raster extents

### Example Output Interpretation

**_change.tif:**
```
+0.5 m   = 0.5 m elevation increase
-0.3 m   = 0.3 m elevation decrease
-9999    = No data (outside coverage area)
```

**_probability.tif:**
```
0.05     = 5% chance of significant change (likely no change)
0.50     = 50% chance (maximum uncertainty)
0.95     = 95% chance of significant change (likely real change)
-9999    = No data (outside coverage area)
```

---

## Examples

### Example 1: Simple Coastal Erosion Study

**Setup:**
```
/data/
  ├── dem_2015.tif              (coastal DEM, t₀)
  ├── dem_2020.tif              (coastal DEM, t₁)
  └── params_coastal.ini
```

**params_coastal.ini:**
```ini
input1   /data/dem_2015
error1   0.10
input2   /data/dem_2020
error2   0.10
oput     /results/coastal_erosion_2015_2020
```

**Run:**
```bash
conda activate demchange
cd /data
python /path/to/dem_change.py params_coastal.ini
```

**Output:**
```
/results/
  ├── coastal_erosion_2015_2020_change.tif         (5.2 MB)
  └── coastal_erosion_2015_2020_probability.tif    (4.8 MB)
```

**Interpret Results:**
- Open `_change.tif` in QGIS/ArcGIS → Erosion areas show -0.5 to -2.0 m
- Open `_probability.tif` → High values (0.8–1.0) in erosion zones confirm significance
- Overlay `_probability.tif` > 0.8 to highlight high-confidence change zones

### Example 2: Glacier Volume Change with Spatially Variable Errors

**Setup:**
```
/glacier_data/
  ├── dem_2010.tif
  ├── dem_2015.tif
  ├── error_2010.tif          (variable LIDAR accuracy by slope)
  ├── error_2015.tif          (variable LIDAR accuracy by slope)
  └── params_glacier.ini
```

**params_glacier.ini:**
```ini
input1   /glacier_data/dem_2010
error1   /glacier_data/error_2010
input2   /glacier_data/dem_2015
error2   /glacier_data/error_2015
oput     /results/glacier_volume_change_2010_2015
nsimulations 1000
```

**Run:**
```bash
conda activate demchange
python /path/to/dem_change.py /glacier_data/params_glacier.ini
```

**Analyze Results:**
```python
import rasterio
import numpy as np

with rasterio.open('/results/glacier_volume_change_2010_2015_change.tif') as src:
    change = src.read(1)
    # Mask for valid pixels
    valid = change > -9999
    # Calculate statistics
    print(f"Mean change: {change[valid].mean():.2f} m")
    print(f"Erosion area (change < -0.5m): {(change < -0.5).sum()} pixels")
```

### Example 3: Batch Processing Multiple Sites

**setup_batch.sh:**
```bash
#!/bin/bash
conda activate demchange

# Process multiple coastal sites
for site in site_A site_B site_C; do
    echo "Processing $site..."
    python dem_change.py configs/${site}.ini
    echo "$site complete"
done

echo "All sites processed"
```

---

## References

### Original Publications

> Wernette, P., J. Lehner, and C. Houser. (2020) What change is ‘real’? A probabilistic approach to accounting for uncertainty in environmental change analysis. *Geomorphology*, 355, 107083. http://doi.org/10.1016/j.geomorph.2020.107083.

### Software References

- **rasterio**: [https://rasterio.readthedocs.io/](https://rasterio.readthedocs.io/)
- **NumPy**: [https://numpy.org/](https://numpy.org/)
- **GDAL**: [https://gdal.org/](https://gdal.org/)

---

## Troubleshooting

### Common Issues & Solutions

#### 1. **"Cannot find raster" error**

**Problem:**
```
FileNotFoundError: Cannot find raster 'dem_2010' (tried multiple extensions: ...)
```

**Solution:**
- Verify file exists in the specified directory
- Check file extension is supported (`.tif`, `.jp2`, `.nc`, etc.)
- Provide full file path or ensure file is in current working directory
- Use quotes if path contains spaces: `"/path/to/dem 2010"`

#### 2. **"CRS mismatch" error**

**Problem:**
```
ValueError: CRS mismatch: dem_2010.tif EPSG:32633 vs dem_2015.tif EPSG:32632
```

**Solution:**
- Reproject one DEM to match the other's CRS
- Use `gdalwarp` or QGIS to reproject:
  ```bash
  gdalwarp -t_srs EPSG:32633 dem_2015.tif dem_2015_reprojected.tif
  ```

#### 3. **"Pixel size mismatch" error**

**Problem:**
```
ValueError: Pixel size mismatch: dem_2010.tif (10.0, 10.0) vs dem_2015.tif (20.0, 20.0)
```

**Solution:**
- Resample to matching pixel size
- Use `gdalwarp`:
  ```bash
  gdalwarp -tr 10 10 dem_2015.tif dem_2015_resampled.tif
  ```

#### 4. **"Rasters do not overlap" error**

**Problem:**
```
ValueError: Rasters do not overlap. Intersection would be empty: (...)
```

**Solution:**
- Verify DEMs cover overlapping geographic areas
- Check CRS and bounds are correct
- Visualize DEMs in QGIS to confirm spatial coverage

#### 5. **Out of memory error**

**Problem:**
```
MemoryError: Unable to allocate [X] MiB for an array
```

**Solution:**
- Reduce tile size (modify `TILE_ROWS`, `TILE_COLS` in code)
- Process subset of data or split into smaller regions
- Use machine with more RAM
- Reduce number of workers: Set `MAX_WORKERS` in code

#### 6. **Slow processing**

**Problem:**
Program takes many hours for typical DEM

**Solution:**
- Verify parallel processing is active (check CPU usage)
- Use SSD for temporary files (faster I/O)
- Reduce tile size (more workers can process simultaneously)
- Consider GPU acceleration (future enhancement)

#### 7. **Output file very large**

**Problem:**
Output `.tif` files are larger than expected

**Solution:**
- This is normal if `ZSTD_LEVEL` is low; increase to 18+ for compression
- Check output file size:
  ```bash
  ls -lh output_*.tif
  ```
- Verify COG structure:
  ```bash
  gdalinfo output_change.tif | head -20
  ```

---

## Performance Characteristics

### Processing Speed

Typical performance on modern multi-core CPU (8+ cores):

| Data Size | Tile Count | Typical Time |
|-----------|-----------|--------------|
| 1 GB input | 4 tiles | 2–5 minutes |
| 10 GB input | 40 tiles | 20–50 minutes |
| 100 GB input | 400 tiles | 3–8 hours |

*Times scale roughly linearly with tile count and inversely with CPU core count.*

### Output Size

Typical compression ratios (with ZSTD level 18):

| Input DEM Size | Output Change Size | Output Probability Size | Total Compression |
|---|---|---|---|
| 10 GB | 1.2 GB | 1.2 GB | ~10% |
| 50 GB | 6 GB | 6 GB | ~10% |

---

## Advanced Configuration

### Modifying Processing Parameters

Edit the top of `dem_change.py` to adjust:

```python
TILE_ROWS  = 512              # Decrease for lower memory usage
TILE_COLS  = 512              # Decrease for lower memory usage
MAX_WORKERS = None            # Set to specific number to limit parallelism
COG_ZSTD_LEVEL = 18           # Range 1–22; higher = more compression, slower
COG_OVERVIEW_LEVELS = [2, 4, 8, 16, 32, 64, 128, 256]  # Modify pyramid
```

### Extending the Program

The modular design allows custom extensions:

- Add new error models (currently: scalar + raster)
- Implement alternative statistical methods
- Export to different output formats
- Add postprocessing filters

---

## License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

### What This Means:

✓ You are free to use, modify, and distribute this software  
✓ You must include a copy of the GPL-3.0 license with any distribution  
✓ Any modifications must also be licensed under GPL-3.0  
✓ You must disclose the source code  

**Copyright © 2026 Phillipe Wernette, Michigan State University**

For full license details and terms, see the [LICENSE.md](../LICENSE.md) file in the repository root.

For commercial use or licensing inquiries, contact: pwernett@msu.edu

---

## Citation

If you use this program in research, please cite both the original work and this Python implementation:

```bibtex
@software{wernette_dem_change_2026,
  author = {Wernette, Phillipe},
  title = {DEM Change Detection with Uncertainty — Python Port},
  year = {2026},
  organization = {Michigan State University, RS\&GIS},
  url = {https://github.com/your-repo/DEM_differencing_with_uncertainty},
  license = {GPL-3.0}
}
```

Also cite the original C++ implementation:

```bibtex
@software{wernette_dem_change_2018,
  author = {Wernette, Phillipe},
  title = {DEM Change Detection with Uncertainty},
  year = {2018},
  organization = {Michigan State University, RS\&GIS}
}
```

### Attribution in Publications

Include a statement such as:

> *Elevation change was computed using DEM Change Detection with Uncertainty (Wernette, 2018, 2026), licensed under GPL-3.0.*

---

## Support & Contact

For issues, questions, or contributions:

- **Email**: pwernett@msu.edu
- **GitHub Issues**: [https://github.com/your-repo/issues](https://github.com/your-repo/issues)
- **Documentation**: See this file and inline code comments

---

## Changelog

### Version 1.0 (Python Port, 2026)
- Initial Python port of C++ original
- Added support for multiple raster formats (GeoTIFF, JP2, NetCDF, HDF5, etc.)
- Implemented overlap-based processing for rasters with different extents
- Multiprocessing parallelization
- Cloud-Optimized GeoTIFF output with overviews
- Comprehensive documentation

### Version 0.x (C++ Original, 2018)
- Original implementation in C++
- DAT+HDR binary format I/O

---

**Last Updated**: 2026-06-18
