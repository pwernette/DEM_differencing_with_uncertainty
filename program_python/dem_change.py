"""
dem_change.py — Probabilistic DEM Change Detection with Uncertainty
=====================================================================

Computes statistically significant elevation changes between two Digital Elevation
Models (DEMs) with spatially variable error surfaces using an analytical approach.

Converted from C++ (datastruct.cpp / main.cpp) by Phillipe Wernette, PhD.
Python port leverages:
  - rasterio: Geospatial raster I/O with windowed reading/writing
  - NumPy: Vectorized mathematical operations for efficient tile processing
  - concurrent.futures: Multiprocessing for parallel tile computation

Core Methodology
----------------
The algorithm computes, for each pixel:
  1. Difference of DEMs (DoD): mu2 - mu1
  2. Probability of significant change: P(change | observations)
     - Based on intersection of two Gaussian PDFs (error distributions)
     - Analytical solution using error function (erf) integral
     - Accounts for spatially variable uncertainty in both epochs

Input Requirements
------------------
  - Two surface DEMs (georeferenced rasters, any extension if listed in params)
  - Two error surfaces (either rasters or scalar global values):
    * Interpreted as 95% confidence interval (±1.96σ)
    * Converted internally to 1-sigma standard deviation
  - All rasters must have identical grid: shape, CRS, and geotransform

Output Format: Cloud-Optimized GeoTIFF (COG)
---------------------------------------------
Two complementary output rasters:
  1. *_change.tif: Raw elevation differences (mu2 - mu1) in same units as input
  2. *_probability.tif: Probability of significant change [0.0, 1.0]
     - 0.0 = high confidence no change
     - 1.0 = high confidence of change
     - 0.5 = maximal uncertainty

COG specifications:
  - ZSTD compression, level 18 (strong compression, acceptable speed)
  - Predictor: 3 (floating-point horizontal differencing for DEM data)
  - BigTIFF enabled (supports outputs > 4 GB)
  - Internal tiling: 512×512 pixels (matches COG standard)
  - Power-of-2 pyramid overviews for efficient visualization/analysis
  - NoData value: -9999.0 (indicating invalid/masked regions)

Processing Strategy: Two-Pass COG
---------------------------------
Pass 1 (sequential, uncompressed writes):
  - Read tiles from input rasters
  - Perform change detection calculations on each tile
  - Write to temporary GeoTIFFs for fast I/O

Pass 2 (finalization with compression):
  - Build overview pyramid on temporary files
  - Copy to final COG layout with ZSTD compression
  - Delete temporary files

Usage
-----
    python dem_change.py [params.ini]

If no params.ini path is provided, defaults to 'params.ini' in current directory.

Configuration File Format: params.ini
-------------------------------------
Whitespace-separated key-value pairs (case-insensitive keys):

    input1          <path_without_extension>    # First DEM (t0)
    error1          <path_without_extension OR float>  # t0 uncertainty (95% CI)
    input2          <path_without_extension>    # Second DEM (t1)
    error2          <path_without_extension OR float>  # t1 uncertainty (95% CI)
    oput            <output_path_without_extension>    # Output base name
    nsimulations    <int>                       # [parsed but unused — analytical method]
    target_epsg     <EPSG code>                 # [OPTIONAL] Reproject to this EPSG code

Example params.ini:
    input1    dem_2010
    error1    0.15
    input2    dem_2015
    error2    error_2015
    oput      dem_change_2010_2015
    nsimulations 100
    target_epsg  4326

Notes
-----
- File extensions (.tif, .tiff, .img, .dat) may be omitted in params.ini
  The script attempts to resolve them automatically
- Error rasters may be:
  * Global scalars (single value applied to all pixels)
  * Spatially variable rasters (one value per pixel)
- Missing or invalid data is detected as values <= NODATA_IN (-9999.0)
  These regions produce NoData outputs (-9999.0)
- Parallel processing uses all available CPU cores (configurable via MAX_WORKERS)
- target_epsg is OPTIONAL: if provided, output rasters are reprojected to that EPSG code
  (e.g., 4326 for WGS84, 3857 for Web Mercator)
  Reprojected outputs are saved with _epsg{code} suffix

References
----------
Original C++ implementation:
  - datastruct.cpp: Core analytical computation
  - main.cpp: I/O and orchestration

Python dependencies:
  - rasterio >= 1.3
  - numpy >= 1.20
  - GDAL >= 3.5 (for COG and ZSTD support)

Author
------
Phillipe Wernette, PhD (pwernett@msu.edu)
Michigan State University, Remote Sensing & GIS Research and Outreach Services (RS&GIS)

Releases
--------
C++ original: 2018
Python port: 2026
"""

import sys
import os
import math
import logging
import warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import rasterio
import rasterio.shutil as rio_shutil
from rasterio.enums import Resampling
from rasterio.windows import Window
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from rasterio.vrt import WarpedVRT

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, **kwargs):
        """Fallback if tqdm is not available."""
        return iterable

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NODATA_IN  = -9999.0   # nodata threshold used during masking
NODATA_OUT = -9999.0   # written to output where data are invalid
TILE_ROWS  = 512        # window height (rows per tile) — also COG internal tile height
TILE_COLS  = 512        # window width  (cols per tile) — also COG internal tile width
MAX_WORKERS = None      # None → use os.cpu_count(); set an int to cap workers

# ---------------------------------------------------------------------------
# COG output settings
# ---------------------------------------------------------------------------
COG_COMPRESS      = "zstd"
COG_ZSTD_LEVEL    = 18          # 1-22; 18 gives strong compression with acceptable speed
COG_PREDICTOR     = 3           # 3 = floating-point horizontal differencing (best for float32 DEMs)
COG_BIGTIFF       = "YES"       # always write BigTIFF -- safe for > 4 GB outputs
COG_OVERVIEW_RESAMPLING = Resampling.average   # appropriate for continuous float surfaces
# Overview levels: powers of 2 until the overview fits in roughly one tile
COG_OVERVIEW_LEVELS = [2, 4, 8, 16, 32, 64, 128, 256]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parameter loading  (mirrors Params::LoadInParameters)
# ---------------------------------------------------------------------------

def load_params(ini_path: str = "params.ini") -> dict:
    """
    Load and parse configuration parameters from an INI file.

    Parameters
    ----------
    ini_path : str, optional
        Path to the parameters file. Default is "params.ini".

    Returns
    -------
    dict
        Dictionary containing parsed parameters with keys:
        - "input1": Path to first DEM (without extension)
        - "error1": Path or scalar value for first error surface
        - "input2": Path to second DEM (without extension)
        - "error2": Path or scalar value for second error surface
        - "oput": Output file base name (without extension)
        - "nsimulations": Number of simulations (str, parsed but not used)

    Raises
    ------
    FileNotFoundError
        If the specified ini_path does not exist.
    ValueError
        If any required parameter is missing.

    Notes
    -----
    - File is parsed as whitespace-separated tokens
    - Parameter names are case-insensitive (converted to lowercase)
    - Required parameters: input1, error1, input2, error2, oput
    - nsimulations defaults to "100" if not specified
    """
    p = {}
    try:
        with open(ini_path) as fh:
            tokens = fh.read().split()
    except FileNotFoundError:
        raise FileNotFoundError(f"Cannot find '{ini_path}'")

    keys = ("input1", "error1", "input2", "error2", "oput", "nsimulations", "target_epsg")
    it = iter(tokens)
    for token in it:
        key = token.lower()
        if key in keys:
            p[key] = next(it)

    for required in ("input1", "error1", "input2", "error2", "oput"):
        if required not in p:
            raise ValueError(f"Missing required key '{required}' in {ini_path}")

    p.setdefault("nsimulations", "100")
    p.setdefault("target_epsg", None)  # Optional: None means no reprojection
    log.info("Parameters loaded from %s", ini_path)
    return p


def is_float(s: str) -> bool:
    """
    Check if a string represents a valid floating-point number.

    Parameters
    ----------
    s : str
        String to test.

    Returns
    -------
    bool
        True if s can be parsed as a float, False otherwise.

    Notes
    -----
    Used to distinguish between global error values (single float) and
    error raster paths in the parameters file.
    """
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Raster helpers
# ---------------------------------------------------------------------------

def open_raster(base_path: str) -> rasterio.DatasetReader:
    """
    Open a georeferenced raster file, automatically resolving file extension.

    Attempts to open the file with various common extensions if the base path
    does not exist directly. This mimics the original C++ behavior, allowing
    configuration files to specify paths without extensions.

    Parameters
    ----------
    base_path : str
        Path to raster file, with or without extension.

    Returns
    -------
    rasterio.DatasetReader
        Opened raster dataset.

    Raises
    ------
    FileNotFoundError
        If the raster cannot be found with any of the tried extensions.

    Supported Formats
    ------------------
    Via rasterio/GDAL, this function can open:
      - GeoTIFF (.tif, .tiff) and COG
      - JPEG2000 (.jp2, .j2k)
      - ERDAS Imagine (.img)
      - NetCDF (.nc)
      - HDF5 (.h5, .hdf5)
      - Virtual Raster (.vrt)
      - ArcGIS ASCII Grid (.asc, .grd)
      - GRIB (.grb, .grib)
      - Binary with header (.dat, .hdr)
      - And many others supported by GDAL

    Notes
    -----
    Extension resolution order:
      1. Exact path as provided
      2. GeoTIFF variants (.tif, .tiff)
      3. JPEG2000 (.jp2, .j2k)
      4. ERDAS Imagine (.img)
      5. NetCDF (.nc)
      6. HDF5 (.h5, .hdf5)
      7. Virtual Raster (.vrt)
      8. ArcGIS Grid (.asc, .grd)
      9. GRIB (.grb, .grib)
      10. Binary with header (.dat, .hdr)

    Examples
    --------
    >>> with open_raster("dem_2010") as src:
    ...     print(src.crs, src.bounds)
    >>> with open_raster("dem_2010.jp2") as src:
    ...     data = src.read(1)
    """
    candidates = [
        base_path,
        # GeoTIFF / Cloud-Optimized GeoTIFF
        base_path + ".tif",
        base_path + ".tiff",
        # JPEG2000
        base_path + ".jp2",
        base_path + ".j2k",
        # ERDAS Imagine
        base_path + ".img",
        # NetCDF
        base_path + ".nc",
        # HDF5
        base_path + ".h5",
        base_path + ".hdf5",
        # Virtual Raster
        base_path + ".vrt",
        # ArcGIS Grid
        base_path + ".asc",
        base_path + ".grd",
        # GRIB
        base_path + ".grb",
        base_path + ".grib",
        # Binary with header (original DAT+HDR)
        base_path + ".dat",
        base_path + ".hdr",
    ]
    
    for c in candidates:
        if Path(c).exists():
            try:
                return rasterio.open(c)
            except Exception as e:
                log.debug(f"Failed to open {c}: {e}")
                continue
    
    raise FileNotFoundError(
        f"Cannot find raster '{base_path}' (tried multiple extensions: "
        ".tif/.tiff/.jp2/.j2k/.img/.nc/.h5/.hdf5/.vrt/.asc/.grd/.grb/.grib/.dat/.hdr)"
    )


def check_compatible(src1: rasterio.DatasetReader,
                     src2: rasterio.DatasetReader) -> None:
    """
    Verify that two raster datasets are spatially compatible for overlap analysis.

    Parameters
    ----------
    src1, src2 : rasterio.DatasetReader
        Raster datasets to compare.

    Raises
    ------
    ValueError
        If rasters have different CRS or pixel sizes (resolutions).

    Notes
    -----
    Checks that:
      - Coordinate Reference System (CRS) is identical
      - Pixel size (resolution) is identical
    This allows rasters to have different extents and origins, but requires
    consistent projection and grid alignment for proper overlap computation.
    """
    if src1.crs != src2.crs:
        raise ValueError(
            f"CRS mismatch: {src1.name} {src1.crs} vs {src2.name} {src2.crs}"
        )
    # Check that pixel sizes (resolutions) are compatible
    # Extract pixel size from transform (assumes axis-aligned pixels)
    ps1 = (src1.transform[0], abs(src1.transform[4]))
    ps2 = (src2.transform[0], abs(src2.transform[4]))
    if not np.allclose(ps1, ps2, rtol=1e-6):
        raise ValueError(
            f"Pixel size mismatch: {src1.name} {ps1} vs {src2.name} {ps2}"
        )


def get_raster_bounds(dataset: rasterio.DatasetReader) -> tuple:
    """
    Get geographic bounds (minx, miny, maxx, maxy) of a raster.

    Parameters
    ----------
    dataset : rasterio.DatasetReader
        Raster dataset.

    Returns
    -------
    tuple (minx, miny, maxx, maxy)
        Geographic coordinates of raster extent.
    """
    bounds = dataset.bounds
    return (bounds.left, bounds.bottom, bounds.right, bounds.top)


def compute_intersection_bounds(bounds_list: list) -> tuple:
    """
    Compute the geographic intersection of multiple raster bounds.

    Parameters
    ----------
    bounds_list : list of tuple
        List of (minx, miny, maxx, maxy) bounds.

    Returns
    -------
    tuple (minx, miny, maxx, maxy)
        Intersection bounds. Raises error if no overlap.

    Raises
    ------
    ValueError
        If rasters do not overlap.
    """
    minx = max(b[0] for b in bounds_list)
    miny = max(b[1] for b in bounds_list)
    maxx = min(b[2] for b in bounds_list)
    maxy = min(b[3] for b in bounds_list)
    
    if minx >= maxx or miny >= maxy:
        raise ValueError(
            f"Rasters do not overlap. Intersection would be empty: "
            f"({minx}, {miny}, {maxx}, {maxy})"
        )
    return (minx, miny, maxx, maxy)


def geo_to_window(dataset: rasterio.DatasetReader,
                  minx: float, miny: float, maxx: float, maxy: float) -> Window:
    """
    Convert geographic bounds to a rasterio Window for a specific raster.

    Parameters
    ----------
    dataset : rasterio.DatasetReader
        Raster dataset.
    minx, miny, maxx, maxy : float
        Geographic bounds.

    Returns
    -------
    rasterio.windows.Window
        Window that covers the geographic region within the raster.
    """
    from rasterio.windows import from_bounds
    return from_bounds(minx, miny, maxx, maxy, dataset.transform)


def build_windows(bounds_tuple: tuple,
                  pixel_size: float,
                  tile_rows: int = TILE_ROWS,
                  tile_cols: int = TILE_COLS):
    """
    Generate windowed regions tiling an extent at a given pixel resolution.

    Parameters
    ----------
    bounds_tuple : tuple (minx, miny, maxx, maxy)
        Geographic bounds to tile.
    pixel_size : float
        Pixel size in geographic units (assumes square pixels).
    tile_rows : int, optional
        Height of each tile in pixels. Default: TILE_ROWS (512).
    tile_cols : int, optional
        Width of each tile in pixels. Default: TILE_COLS (512).

    Yields
    ------
    tuple (minx_tile, miny_tile, window)
        - minx_tile, miny_tile (float): Geographic coordinates of tile origin
        - window (rasterio.windows.Window): Window in output grid coordinates

    Notes
    -----
    - Tiles cover the entire extent
    - Edge tiles are smaller if extent does not align with tile boundaries
    - Each tile is defined both geographically (for reference) and as a window
    """
    minx, miny, maxx, maxy = bounds_tuple
    width_geo = maxx - minx
    height_geo = maxy - miny
    
    # Convert geographic size to pixel counts
    total_cols = int(np.ceil(width_geo / pixel_size))
    total_rows = int(np.ceil(height_geo / pixel_size))
    
    for row_off in range(0, total_rows, tile_rows):
        actual_rows = min(tile_rows, total_rows - row_off)
        miny_tile = maxy - (row_off + actual_rows) * pixel_size  # Top-down
        
        for col_off in range(0, total_cols, tile_cols):
            actual_cols = min(tile_cols, total_cols - col_off)
            minx_tile = minx + col_off * pixel_size
            
            # Create window in output grid coordinates
            window = Window(col_off, row_off, actual_cols, actual_rows)
            yield minx_tile, miny_tile, window


# ---------------------------------------------------------------------------
# Core per-pixel analytical computation  (vectorised NumPy version of
# OutRaster::pchange from datastruct.cpp)
# ---------------------------------------------------------------------------

def _intersection_point(mu_lo, sd_lo, mu_hi, sd_hi):
    """
    Compute the intersection point of two Gaussian probability density functions.

    For two Gaussian distributions with means mu_lo < mu_hi and standard
    deviations sd_lo and sd_hi, find the x-coordinate where their PDFs intersect.
    This point is used as the threshold in the change probability calculation.

    Parameters
    ----------
    mu_lo : float or np.ndarray
        Mean of lower distribution(s).
    sd_lo : float or np.ndarray
        Standard deviation of lower distribution(s).
    mu_hi : float or np.ndarray
        Mean of higher distribution(s).
    sd_hi : float or np.ndarray
        Standard deviation of higher distribution(s).

    Returns
    -------
    float or np.ndarray
        Intersection point(s) c of the PDFs.

    Notes
    -----
    Formula (from C++ original):

        c = (mu_hi * 2^sd_lo - sd_hi * (mu_lo*sd_hi +
              sd_lo + sqrt(2^(mu_lo-mu_hi) +
              2*(2^sd_lo - 2^sd_hi)*ln(sd_lo/sd_hi))))
            / (2^sd_lo - sd_hi)

    IMPORTANT: The original C++ source uses pow(2.0, x) to compute 2^x
    (not x^2). While this appears unusual and may be a typo, the Python
    translation preserves this exact formula for consistency with the
    C++ reference implementation. Results may differ if the formula
    should actually use squared terms.

    RuntimeWarnings (square root of negative) are suppressed and produce NaN
    values, which are typically masked in downstream processing.
    """
    # Original C++ line (mu1 < mu2 branch, with mu1=mu_lo, mu2=mu_hi):
    #   float c = ((mu2*(pow(2.0,sd1)))-(sd2*((mu1*sd2)+(sd1+sqrt(
    #              (pow(2.0,mu1-mu2))+(2*(pow(2.0,sd1)-pow(2.0,sd2))*log(sd1/sd2))
    #              )))))/(pow(2.0,sd1)-(sd2));
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        inner = (
            np.power(2.0, mu_lo - mu_hi)
            + 2.0 * (np.power(2.0, sd_lo) - np.power(2.0, sd_hi))
            * np.log(sd_lo / sd_hi)
        )
        sqrt_term = np.where(inner >= 0, np.sqrt(np.maximum(inner, 0.0)), np.nan)
        numerator = (
            mu_hi * np.power(2.0, sd_lo)
            - sd_hi * (mu_lo * sd_hi + sd_lo + sqrt_term)
        )
        denominator = np.power(2.0, sd_lo) - sd_hi
        c = np.where(denominator != 0, numerator / denominator, np.nan)
    return c


def _prob_from_intersection(c, mu_lo, sd_lo, mu_hi, _sd_hi):
    """
    Compute probability of change from the intersection point of two Gaussians.

    Integrates the area under the lower PDF to the right of the intersection
    point c, giving the probability that observations from the lower distribution
    exceed the intersection point (indicating significant change).

    Parameters
    ----------
    c : float or np.ndarray
        Intersection point(s) of the two PDFs.
    mu_lo : float or np.ndarray
        Mean of lower distribution(s).
    sd_lo : float or np.ndarray
        Standard deviation of lower distribution(s).
    mu_hi : float or np.ndarray
        Mean of higher distribution(s).
    _sd_hi : float or np.ndarray
        Standard deviation of higher distribution(s). Unused; kept for signature consistency.

    Returns
    -------
    float or np.ndarray
        Probability of change in range [0, 1].

    Notes
    -----
    Formula (from C++ original, vectorized):

        P(change) = 1 - 0.5*erf((c - mu_lo) / (sqrt(2)*sd_lo))
                      + 0.5*erf((c - mu_hi) / (sqrt(2)*sd_lo))

    Note: Both erf terms use sd_lo (not sd_hi in the second term).
    This matches the C++ source exactly but may warrant review.

    The result is bounded to [0, 1] and represents the probability that
    the measured change is statistically significant given the uncertainties.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sqrt2_sd = np.sqrt(2.0) * sd_lo
        prob = (
            1.0
            - 0.5 * np.where(sqrt2_sd != 0,
                              np.vectorize(math.erf)((c - mu_lo) / sqrt2_sd),
                              0.0)
            + 0.5 * np.where(sqrt2_sd != 0,
                              np.vectorize(math.erf)((c - mu_hi) / sqrt2_sd),
                              0.0)
        )
    return prob


def reproject_raster(src_path: str, dst_path: str, target_epsg: int) -> None:
    """
    Reproject a raster to a target EPSG coordinate system.

    Creates a reprojected Cloud-Optimized GeoTIFF with the same compression
    and internal tiling as the original.

    Parameters
    ----------
    src_path : str
        Path to source GeoTIFF.
    dst_path : str
        Path to output reprojected GeoTIFF.
    target_epsg : int
        Target EPSG code (e.g., 3857 for Web Mercator, 4326 for WGS84).

    Raises
    ------
    ValueError
        If target EPSG code is invalid or reprojection fails.

    Notes
    -----
    - Output maintains COG format with ZSTD compression
    - Uses nearest-neighbor resampling for categorical data
    - Preserves NoData values
    """
    try:
        target_crs = CRS.from_epsg(target_epsg)
    except Exception as e:
        log.error("Failed to create CRS from EPSG:%d: %s", target_epsg, str(e))
        log.error("This may be due to PROJ database issues in your environment.")
        log.error("Skipping reprojection.")
        raise
    
    with rasterio.open(src_path) as src:
        # Check if already in target CRS
        if src.crs == target_crs:
            log.info("  Source already in target CRS (EPSG:%d), skipping reprojection", target_epsg)
            return
        
        log.info("  Reprojecting from %s to EPSG:%d", src.crs, target_epsg)
        
        # Use WarpedVRT to read data in target CRS
        with WarpedVRT(src, crs=target_crs, resampling=Resampling.bilinear) as vrt:
            # Create output profile based on warped data
            profile = vrt.profile.copy()
            profile.update(
                driver="GTiff",
                compress=COG_COMPRESS,
                zstd_level=COG_ZSTD_LEVEL,
                predictor=COG_PREDICTOR,
                tiled=True,
                blockxsize=TILE_COLS,
                blockysize=TILE_ROWS,
                bigtiff=COG_BIGTIFF,
            )
            
            # Write reprojected raster
            with rasterio.open(dst_path, "w", **profile) as dst:
                # Copy data band by band
                for i in range(1, src.count + 1):
                    data = vrt.read(i)
                    dst.write(data, i)


def reproject_outputs(change_path: str, prob_path: str, target_epsg: int) -> tuple:
    """
    Reproject both output rasters to a target EPSG code.

    Parameters
    ----------
    change_path : str
        Path to change raster output.
    prob_path : str
        Path to probability raster output.
    target_epsg : int
        Target EPSG code.

    Returns
    -------
    tuple (reprojected_change_path, reprojected_prob_path)
        Paths to reprojected output files (with _epsg{code} suffix).
    """
    base_change = change_path.rsplit(".", 1)[0]  # Remove extension
    base_prob = prob_path.rsplit(".", 1)[0]
    
    reprojected_change = f"{base_change}_epsg{target_epsg}.tif"
    reprojected_prob = f"{base_prob}_epsg{target_epsg}.tif"
    
    log.info("\n--- REPROJECTION (PASS 3) ---")
    log.info("Reprojecting outputs to EPSG:%d", target_epsg)
    
    reproject_raster(change_path, reprojected_change, target_epsg)
    reproject_raster(prob_path, reprojected_prob, target_epsg)
    
    return reprojected_change, reprojected_prob


def compute_tile(mu1: np.ndarray,
                 sd1: np.ndarray,
                 mu2: np.ndarray,
                 sd2: np.ndarray,
                 nodata_in: float = NODATA_IN,
                 nodata_out: float = NODATA_OUT):
    """
    Vectorized change detection computation for one raster tile.

    For each pixel, computes:
      1. Difference of DEMs (DoD): mu2 - mu1
      2. Probability of significant change based on error distributions

    Parameters
    ----------
    mu1 : np.ndarray (float32)
        First surface values (e.g., DEM at time t0).
    sd1 : np.ndarray (float32)
        Standard deviations for first surface (already in 1-sigma units,
        i.e., converted from 95% CI by division by 1.96).
    mu2 : np.ndarray (float32)
        Second surface values (e.g., DEM at time t1).
    sd2 : np.ndarray (float32)
        Standard deviations for second surface (1-sigma units).
    nodata_in : float, optional
        Threshold for input masking. Pixels with values <= nodata_in are
        treated as missing. Default: NODATA_IN (-9999.0).
    nodata_out : float, optional
        Value written for invalid/missing output pixels. Default: NODATA_OUT (-9999.0).

    Returns
    -------
    change : np.ndarray (float32)
        Elevation differences (mu2 - mu1). NoData where inputs are invalid.
    prob : np.ndarray (float32)
        Probability of significant change [0.0, 1.0]. NoData where inputs are invalid.

    Notes
    -----
    - All inputs must have the same shape
    - Computation is vectorized using NumPy for efficiency
    - Two branches:
      * mu2 > mu1: Uses lower=mu1/sd1, higher=mu2/sd2
      * mu2 < mu1: Uses lower=mu2/sd2, higher=mu1/sd1 (flipped for symmetry)
    - Pixels with mu1 == mu2 produce change=0, prob computed accordingly
    """
    change = np.full(mu1.shape, nodata_out, dtype=np.float32)
    prob   = np.full(mu1.shape, nodata_out, dtype=np.float32)

    valid = (mu1 > nodata_in) & (mu2 > nodata_in)

    # --- DoD (difference of DEMs) ----------------------------------------
    change[valid] = (mu2 - mu1)[valid]

    # --- mu2 > mu1 branch ---------------------------------------------------
    m1_lt_m2 = valid & (mu1 < mu2)
    if m1_lt_m2.any():
        c = _intersection_point(mu1[m1_lt_m2], sd1[m1_lt_m2],
                                mu2[m1_lt_m2], sd2[m1_lt_m2])
        prob[m1_lt_m2] = _prob_from_intersection(
            c, mu1[m1_lt_m2], sd1[m1_lt_m2], mu2[m1_lt_m2], sd2[m1_lt_m2]
        )

    # --- mu2 < mu1 branch  (mu/sd labels are flipped in C++ source) -------
    m2_lt_m1 = valid & (mu2 < mu1)
    if m2_lt_m1.any():
        c = _intersection_point(mu2[m2_lt_m1], sd2[m2_lt_m1],
                                mu1[m2_lt_m1], sd1[m2_lt_m1])
        prob[m2_lt_m1] = _prob_from_intersection(
            c, mu2[m2_lt_m1], sd2[m2_lt_m1], mu1[m2_lt_m1], sd1[m2_lt_m1]
        )

    return change, prob


# ---------------------------------------------------------------------------
# Worker function executed in a subprocess (for parallel processing)
# ---------------------------------------------------------------------------

def _process_window(args):
    """
    Worker function for parallel tile processing (executed in subprocess).

    Reads one raster window/tile from input DEMs and error surfaces using
    geographic coordinates, handles rasters with different extents by
    converting geographic bounds to local windows for each raster.

    Parameters
    ----------
    args : tuple
        (minx_tile, miny_tile, window, paths_dict, global_errors, raster_metadata)

        - minx_tile, miny_tile (float): Geographic coordinates of tile origin
        - window : rasterio.windows.Window
            Window in output grid coordinates (for result placement)
        - paths_dict : dict
            Keys: "s1", "s2", "se1", "se2"
            Values: File paths with extensions resolved
        - global_errors : dict
            Keys: "se1", "se2"
            Values: float (if global error) or None (if raster error)
        - raster_metadata : dict
            Metadata for each raster (transform, bounds) for coordinate conversion

    Returns
    -------
    tuple (window, change_tile, prob_tile)
        - window : rasterio.windows.Window
            Same as input (for result placement)
        - change_tile : np.ndarray (float32)
            DEM difference for this window
        - prob_tile : np.ndarray (float32)
            Probability of change for this window

    Notes
    -----
    - Handles rasters with different extents (clips to overlap region)
    - Converts geographic bounds to local window coordinates for each raster
    - Missing areas (outside a raster's extent) are filled with NoData
    """
    minx_tile, miny_tile, window, paths, global_errors, metadata = args
    
    # Calculate geographic bounds of this tile
    pixel_size = metadata["pixel_size"]
    maxx_tile = minx_tile + window.width * pixel_size
    maxy_tile = miny_tile + window.height * pixel_size
    
    # Read surface rasters, converting geographic bounds to local windows
    # Handle potential out-of-bounds reads gracefully
    def safe_read_window(path, minx, miny, maxx, maxy):
        """Read from a window that may be partially outside the raster extent."""
        with rasterio.open(path) as ds:
            # Check if window overlaps raster extent
            raster_bounds = ds.bounds
            if (maxx <= raster_bounds.left or minx >= raster_bounds.right or
                maxy <= raster_bounds.bottom or miny >= raster_bounds.top):
                # No overlap, return NoData array
                nodata_val = ds.nodata if ds.nodata is not None else NODATA_IN
                return np.full((int(np.ceil((maxy - miny) / pixel_size)),
                               int(np.ceil((maxx - minx) / pixel_size))),
                              nodata_val, dtype=np.float32)
            
            # Clip to raster extent and convert to local window
            local_minx = max(minx, raster_bounds.left)
            local_miny = max(miny, raster_bounds.bottom)
            local_maxx = min(maxx, raster_bounds.right)
            local_maxy = min(maxy, raster_bounds.top)
            
            try:
                from rasterio.windows import from_bounds
                local_window = from_bounds(local_minx, local_miny, local_maxx, local_maxy, ds.transform)
                data = ds.read(1, window=local_window).astype(np.float32)
                nodata_val = ds.nodata if ds.nodata is not None else NODATA_IN
                return data, nodata_val
            except Exception:
                # Window read failed, return NoData
                nodata_val = ds.nodata if ds.nodata is not None else NODATA_IN
                return np.full((int(np.ceil((maxy - miny) / pixel_size)),
                               int(np.ceil((maxx - minx) / pixel_size))),
                              nodata_val, dtype=np.float32)
    
    # Read DEMs
    mu1, nodata1 = safe_read_window(paths["s1"], minx_tile, miny_tile, maxx_tile, maxy_tile)
    mu2, nodata2 = safe_read_window(paths["s2"], minx_tile, miny_tile, maxx_tile, maxy_tile)
    
    # Normalize nodata to NODATA_IN sentinel
    mu1 = np.where(mu1 <= nodata1, NODATA_IN, mu1)
    mu2 = np.where(mu2 <= nodata2, NODATA_IN, mu2)
    
    # Build sd arrays (error / 1.96 → 1-sigma)
    if global_errors["se1"] is not None:
        sd1 = np.full_like(mu1, global_errors["se1"] / 1.96)
    else:
        e1, _ = safe_read_window(paths["se1"], minx_tile, miny_tile, maxx_tile, maxy_tile)
        nd = NODATA_IN
        e1 = np.where(e1 <= nd, 0.0, e1)
        sd1 = e1 / 1.96
    
    if global_errors["se2"] is not None:
        sd2 = np.full_like(mu2, global_errors["se2"] / 1.96)
    else:
        e2, _ = safe_read_window(paths["se2"], minx_tile, miny_tile, maxx_tile, maxy_tile)
        nd = NODATA_IN
        e2 = np.where(e2 <= nd, 0.0, e2)
        sd2 = e2 / 1.96
    
    # Guard against zero or negative standard deviations
    sd1 = np.maximum(sd1, 1e-10)
    sd2 = np.maximum(sd2, 1e-10)
    
    change, prob = compute_tile(mu1, sd1, mu2, sd2)
    return window, change, prob


# ---------------------------------------------------------------------------
# Output raster helpers — two-pass COG strategy
# ---------------------------------------------------------------------------

def _temp_profile(ref_src: rasterio.DatasetReader,
                  dtype=np.float32,
                  nodata: float = NODATA_OUT) -> dict:
    """
    Generate rasterio profile for temporary (uncompressed) GeoTIFF in Pass 1.

    Parameters
    ----------
    ref_src : rasterio.DatasetReader
        Reference raster to copy spatial metadata from (CRS, transform, etc.).
    dtype : np.dtype, optional
        Output data type. Default: np.float32.
    nodata : float, optional
        NoData value for output. Default: NODATA_OUT (-9999.0).

    Returns
    -------
    dict
        Profile dictionary suitable for rasterio.open(..., **profile).
        Settings:
        - GTiff format, no compression (fast writes)
        - Tiled layout (512x512 blocks for efficient overview building)
        - BigTIFF enabled (supports large files)
        - Inherits CRS and geotransform from ref_src

    Notes
    -----
    This temporary file is used only during Pass 1 of the two-pass COG strategy.
    It is replaced by the final COG in Pass 2 after overview building.
    """
    profile = ref_src.profile.copy()
    profile.update(
        driver="GTiff",
        dtype=dtype,
        count=1,
        nodata=nodata,
        tiled=True,
        blockxsize=TILE_COLS,
        blockysize=TILE_ROWS,
        bigtiff=COG_BIGTIFF,
        compress="none",
    )
    # Strip any existing overview-related keys that rasterio may have carried over
    profile.pop("overview_level", None)
    return profile


def _cog_profile(ref_src: rasterio.DatasetReader,
                 dtype=np.float32,
                 nodata: float = NODATA_OUT) -> dict:
    """
    Generate rasterio profile for final Cloud-Optimized GeoTIFF (COG) in Pass 2.

    Parameters
    ----------
    ref_src : rasterio.DatasetReader
        Reference raster to copy spatial metadata from (CRS, transform, etc.).
    dtype : np.dtype, optional
        Output data type. Default: np.float32.
    nodata : float, optional
        NoData value for output. Default: NODATA_OUT (-9999.0).

    Returns
    -------
    dict
        Profile dictionary suitable for rasterio.shutil.copy(..., **profile).
        Settings:
        - ZSTD compression (level 18) for efficient storage
        - Predictor 3 (floating-point delta encoding, optimal for DEMs)
        - Tiled layout (512x512 blocks, COG standard)
        - BigTIFF enabled
        - copy_src_overviews=True (copies pyramid from temporary file)
        - Inherits CRS and geotransform from ref_src

    Notes
    -----
    Used in Pass 2 of the two-pass COG strategy. The profile is passed to
    rasterio.shutil.copy() to create the final COG with proper layout,
    compression, and embedded overviews.
    """
    profile = ref_src.profile.copy()
    profile.update(
        driver="GTiff",
        dtype=dtype,
        count=1,
        nodata=nodata,
        tiled=True,
        blockxsize=TILE_COLS,
        blockysize=TILE_ROWS,
        compress=COG_COMPRESS,
        zstd_level=COG_ZSTD_LEVEL,
        predictor=COG_PREDICTOR,
        bigtiff=COG_BIGTIFF,
        copy_src_overviews=True,  # tells GDAL to copy existing overviews into the COG
    )
    profile.pop("overview_level", None)
    return profile


def create_temp_raster(tmp_path: str,
                       ref_src: rasterio.DatasetReader,
                       dtype=np.float32,
                       nodata: float = NODATA_OUT):
    """
    Create and open a temporary GeoTIFF for Pass 1 pixel writing.

    Parameters
    ----------
    tmp_path : str
        File path for the temporary GeoTIFF to create.
    ref_src : rasterio.DatasetReader
        Reference raster dataset to copy geospatial metadata from.
    dtype : np.dtype, optional
        Output data type. Default: np.float32.
    nodata : float, optional
        NoData value. Default: NODATA_OUT (-9999.0).

    Returns
    -------
    rasterio.io.DatasetWriter
        Opened temporary GeoTIFF ready for windowed writes.

    Notes
    -----
    - Created without compression for fast sequential writes during Pass 1
    - Uses tiled layout to enable efficient overview building in Pass 2
    - Should be used as context manager (with statement)
    """
    return rasterio.open(tmp_path, "w", **_temp_profile(ref_src, dtype, nodata))


def finalize_cog(tmp_path: str,
                 cog_path: str,
                 ref_src: rasterio.DatasetReader,
                 dtype=np.float32,
                 nodata: float = NODATA_OUT) -> None:
    """
    Finalize Cloud-Optimized GeoTIFF: build overviews and copy with compression (Pass 2).

    Parameters
    ----------
    tmp_path : str
        Path to temporary GeoTIFF created in Pass 1.
    cog_path : str
        Path for final COG output.
    ref_src : rasterio.DatasetReader
        Reference raster dataset for geospatial metadata.
    dtype : np.dtype, optional
        Data type for output. Default: np.float32.
    nodata : float, optional
        NoData value. Default: NODATA_OUT (-9999.0).

    Notes
    -----
    This function implements Pass 2 of the two-pass COG strategy:

    1. Opens temporary file in read-write mode
    2. Builds power-of-2 pyramid overviews (2, 4, 8, 16, 32, 64, 128, 256)
    3. Trims overview levels to avoid sub-tile pyramids
       (keeps levels where dimension >= 1 full tile)
    4. Copies temporary file to final COG with ZSTD compression and COG layout
    5. Deletes the temporary file

    The embedded overview pyramid enables efficient visualization and analysis
    of large DEMs in GIS software and automated workflows.

    Examples
    --------
    >>> finalize_cog("temp.tif", "dem_final.tif", ref_dataset)
    # Results in properly formatted COG at dem_final.tif
    """
    with rasterio.open(tmp_path, "r+") as tmp:
        nrows, ncols = tmp.height, tmp.width

        # Keep only overview levels where the downsampled dimension >= 1 tile
        min_dim = min(nrows, ncols)
        levels = [lvl for lvl in COG_OVERVIEW_LEVELS
                  if (min_dim // lvl) >= 1]
        if not levels:
            levels = [2]  # always build at least one overview level

        log.info("  Building %d overview level(s): %s", len(levels), levels)
        tmp.build_overviews(levels, COG_OVERVIEW_RESAMPLING)
        tmp.update_tags(ns="rio_overview", resampling=COG_OVERVIEW_RESAMPLING.name)

    log.info("  Copying to COG: %s", cog_path)
    rio_shutil.copy(
        tmp_path,
        cog_path,
        **_cog_profile(ref_src, dtype, nodata),
    )


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main(ini_path: str = "params.ini"):
    """
    Orchestrate the full probabilistic DEM change detection workflow.

    Parameters
    ----------
    ini_path : str, optional
        Path to configuration file (params.ini format). Default: "params.ini".

    Workflow
    --------
    1. Load parameters from ini_path
    2. Open input rasters (DEMs and error surfaces)
    3. Verify spatial compatibility (shape, CRS, resolution)
    4. Resolve file paths with extensions for worker subprocesses
    5. Build tile windows covering entire raster
    6. Pass 1 (parallel processing):
       - Submit tiles to ProcessPoolExecutor
       - Workers read tiles and compute change/probability
       - Results written to temporary uncompressed GeoTIFFs
    7. Pass 2 (finalization):
       - Build power-of-2 overview pyramids on temporary files
       - Copy to final COGs with ZSTD compression
       - Delete temporary files
    8. Log success and output file information

    Output Files
    --------
    Two COG outputs are created (where {oput} is from params.ini):

    - {oput}_change.tif:
        Raw elevation differences (mu2 - mu1)
        Units: same as input DEMs (typically meters)
        Range: typically [-inf, +inf]
        NoData: -9999.0 (in masked regions)

    - {oput}_probability.tif:
        Probability of significant change [0.0, 1.0]
        0.0 = high confidence no significant change
        0.5 = maximal uncertainty
        1.0 = high confidence of significant change
        NoData: -9999.0 (in masked regions)

    Both outputs have:
    - ZSTD compression level 18 (configurable)
    - Power-of-2 overview pyramid for efficient access
    - 512×512 internal tiles (COG standard)
    - Same CRS and geotransform as input DEMs
    """
    print("\n" + "="*70)
    print("  PROBABILISTIC DEM CHANGE DETECTION WITH UNCERTAINTY")
    print("="*70)
    log.info("Starting DEM change detection workflow")
    log.info("Configuration file: %s", ini_path)
    
    params = load_params(ini_path)

    s1_path  = params["input1"]
    s2_path  = params["input2"]
    se1_spec = params["error1"]
    se2_spec = params["error2"]
    out_base = params["oput"]
    target_epsg_str = params.get("target_epsg")  # None if not specified
    target_epsg = None
    if target_epsg_str:
        try:
            target_epsg = int(target_epsg_str)
        except (ValueError, TypeError):
            log.warning("Invalid target_epsg value: %s (skipping reprojection)", target_epsg_str)
            target_epsg = None

    log.info("\n--- INPUT DATA ---")
    log.info("DEM 1 (t0):  %s", s1_path)
    log.info("DEM 2 (t1):  %s", s2_path)
    
    # Determine if error inputs are global scalars or raster paths
    se1_is_float = is_float(se1_spec)
    se2_is_float = is_float(se2_spec)

    global_errors = {
        "se1": float(se1_spec) if se1_is_float else None,
        "se2": float(se2_spec) if se2_is_float else None,
    }

    log.info("\n--- UNCERTAINTY MODELS ---")
    if se1_is_float:
        log.info("Error 1 (t0): Global scalar = %.4f (95%% CI)", global_errors["se1"])
    else:
        log.info("Error 1 (t0): Raster = %s", se1_spec)
    
    if se2_is_float:
        log.info("Error 2 (t1): Global scalar = %.4f (95%% CI)", global_errors["se2"])
    else:
        log.info("Error 2 (t1): Raster = %s", se2_spec)

    # Open reference rasters to verify compatibility and read metadata
    with open_raster(s1_path) as src1, open_raster(s2_path) as src2:
        check_compatible(src1, src2)

        if not se1_is_float:
            with open_raster(se1_spec) as sre1:
                check_compatible(src1, sre1)
        if not se2_is_float:
            with open_raster(se2_spec) as sre2:
                check_compatible(src1, sre2)

        # Calculate intersection bounds of all input rasters
        bounds_list = [get_raster_bounds(src1), get_raster_bounds(src2)]
        if not se1_is_float:
            with open_raster(se1_spec) as sre1:
                bounds_list.append(get_raster_bounds(sre1))
        if not se2_is_float:
            with open_raster(se2_spec) as sre2:
                bounds_list.append(get_raster_bounds(sre2))
        
        intersect_bounds = compute_intersection_bounds(bounds_list)
        log.info("\n--- SPATIAL ANALYSIS ---")
        log.info("CRS: %s", src1.crs)
        log.info("Pixel size: %.4f x %.4f", abs(src1.transform[0]), abs(src1.transform[4]))
        log.info("Intersection bounds: minx=%.2f, miny=%.2f, maxx=%.2f, maxy=%.2f", *intersect_bounds)

        # Extract pixel size from first raster
        pixel_size = abs(src1.transform[0])
        
        # Resolve actual file paths (with extension) for worker subprocesses
        paths = {
            "s1":  open_raster(s1_path).name,
            "s2":  open_raster(s2_path).name,
            "se1": None if se1_is_float else open_raster(se1_spec).name,
            "se2": None if se2_is_float else open_raster(se2_spec).name,
        }
        
        # Metadata for coordinate conversion in workers
        raster_metadata = {
            "pixel_size": pixel_size,
        }

        # Build windows over the intersection extent
        windows = list(build_windows(intersect_bounds, pixel_size, TILE_ROWS, TILE_COLS))
        n_tiles = len(windows)
        log.info("\n--- TILING STRATEGY ---")
        log.info("Total tiles to process: %d (%d×%d pixels each)", n_tiles, TILE_ROWS, TILE_COLS)

        # Create output raster profile with intersection extent
        # Use src1 as reference for CRS
        output_bounds = intersect_bounds
        output_height = int(np.ceil((output_bounds[3] - output_bounds[1]) / pixel_size))
        output_width = int(np.ceil((output_bounds[2] - output_bounds[0]) / pixel_size))
        
        # Create a transform for the output raster
        output_transform = from_bounds(*output_bounds, output_width, output_height)
        
        # Output paths (using os.path.join for cross-platform compatibility)
        out_dir = os.path.dirname(out_base) or "."
        out_name = os.path.basename(out_base)
        change_path = os.path.join(out_dir, out_name + "_change.tif")
        prob_path = os.path.join(out_dir, out_name + "_probability.tif")
        change_tmp_path = os.path.join(out_dir, out_name + "_change_tmp.tif")
        prob_tmp_path = os.path.join(out_dir, out_name + "_probability_tmp.tif")

        # ── Pass 1: write pixel data to temp (uncompressed) GeoTIFFs ────────
        log.info("\n--- PASS 1: DATA PROCESSING & TILE WRITING ---")
        log.info("Processing %d tiles in parallel...", n_tiles)
        if HAS_TQDM:
            log.info("(Progress bar enabled with tqdm)")
        
        # Create output profiles with intersection extent
        output_profile_change = src1.profile.copy()
        output_profile_change.update(
            driver="GTiff",
            dtype=np.float32,
            count=1,
            nodata=NODATA_OUT,
            height=output_height,
            width=output_width,
            transform=output_transform,
            tiled=True,
            blockxsize=TILE_COLS,
            blockysize=TILE_ROWS,
            bigtiff=COG_BIGTIFF,
            compress="none",
        )
        output_profile_change.pop("overview_level", None)
        
        output_profile_prob = output_profile_change.copy()
        
        with (
            rasterio.open(change_tmp_path, "w", **output_profile_change) as dst_change,
            rasterio.open(prob_tmp_path, "w", **output_profile_prob) as dst_prob):
                work_args = [
                    (minx_tile, miny_tile, win, paths, global_errors, raster_metadata)
                    for minx_tile, miny_tile, win in windows
                ]

                completed = 0
                with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
                    futures = {
                        pool.submit(_process_window, arg): arg
                        for arg in work_args
                    }
                    # Use tqdm for progress bar if available
                    futures_iter = tqdm(as_completed(futures), total=len(futures), 
                                       desc="Processing tiles", unit="tile", disable=not HAS_TQDM)
                    for future in futures_iter:
                        try:
                            win, change_tile, prob_tile = future.result()
                        except Exception as exc:
                            log.error("Tile at window %s failed: %s", win, exc)
                            continue

                        dst_change.write(change_tile[np.newaxis, :, :], window=win)
                        dst_prob.write(prob_tile[np.newaxis, :, :],     window=win)

                        completed += 1
                        if completed % max(1, n_tiles // 10) == 0 or completed == n_tiles:
                            pct = 100 * completed / n_tiles
                            log.info("  Progress: %d / %d tiles (%.1f%%)",
                                    completed, n_tiles, pct)

        # ── Pass 2: build overviews + copy to final COG ──────────────────────
        log.info("\n--- PASS 2: FINALIZATION (OVERVIEWS & COMPRESSION) ---")

        # Process change raster
        with rasterio.open(change_tmp_path) as tmp_src:
            log.info("  Building overviews and compressing change raster...")
            finalize_cog(change_tmp_path, change_path, tmp_src)
        # Close the file handle before deleting
        Path(change_tmp_path).unlink()

        # Process probability raster
        with rasterio.open(prob_tmp_path) as tmp_src:
            log.info("  Building overviews and compressing probability raster...")
            finalize_cog(prob_tmp_path, prob_path, tmp_src)
        # Close the file handle before deleting
        Path(prob_tmp_path).unlink()

    # Final summary
    log.info("\n" + "="*70)
    log.info("WORKFLOW COMPLETE")
    log.info("="*70)
    log.info("\n--- OUTPUT FILES ---")
    log.info("✓ Change raster (elevation difference):")
    log.info("  Location: %s", os.path.abspath(change_path))
    log.info("  Size: %d × %d pixels", output_width, output_height)
    log.info("  CRS: %s", src1.crs)
    log.info("  Units: Same as input DEMs (typically meters)")
    log.info("  Compression: ZSTD level %d with predictor %d", COG_ZSTD_LEVEL, COG_PREDICTOR)
    log.info("\n✓ Probability raster (significance of change):")
    log.info("  Location: %s", os.path.abspath(prob_path))
    log.info("  Size: %d × %d pixels", output_width, output_height)
    log.info("  CRS: %s", src1.crs)
    log.info("  Range: [0.0 = no change confidence, 1.0 = significant change confidence]")
    log.info("  Compression: ZSTD level %d with predictor %d", COG_ZSTD_LEVEL, COG_PREDICTOR)
    
    # Handle optional reprojection
    if target_epsg is not None:
        try:
            reprojected_change, reprojected_prob = reproject_outputs(change_path, prob_path, target_epsg)
            log.info("\n✓ Reprojected change raster (EPSG:%d):")
            log.info("  Location: %s", os.path.abspath(reprojected_change))
            log.info("\n✓ Reprojected probability raster (EPSG:%d):")
            log.info("  Location: %s", os.path.abspath(reprojected_prob))
            final_change = reprojected_change
            final_prob = reprojected_prob
        except Exception as e:
            log.error("\n✗ Reprojection failed: %s", str(e))
            log.error("Possible cause: PROJ database version mismatch in your conda environment.")
            log.error("Continuing with original (non-reprojected) output files.")
            log.error("To fix this, try: conda install -c conda-forge proj gdal")
            final_change = change_path
            final_prob = prob_path
    else:
        final_change = change_path
        final_prob = prob_path
    
    log.info("\n--- SUMMARY ---")
    log.info("Output directory: %s", os.path.abspath(out_dir))
    log.info("All output files are Cloud-Optimized GeoTIFFs (COG) with embedded pyramids")
    log.info("\n" + "="*70 + "\n")
    
    print("\n" + "="*70)
    print("  ✓ SUCCESS: Output files are ready!")
    print("  ")
    print(f"  Change raster:      {os.path.abspath(final_change)}")
    print(f"  Probability raster: {os.path.abspath(final_prob)}")
    if target_epsg is not None:
        print(f"  (Reprojected to EPSG:{target_epsg})")
    print("="*70 + "\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ini = sys.argv[1] if len(sys.argv) > 1 else "params.ini"
    main(ini)
