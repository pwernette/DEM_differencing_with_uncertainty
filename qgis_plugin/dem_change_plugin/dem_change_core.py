"""
dem_change_core.py
------------------
Core DEM change detection logic, ported from dem_change.py.

This module is intentionally decoupled from the QGIS Processing API so it
can also be used as a standalone script or imported by other tools.

The only QGIS coupling is the optional *feedback* argument (a
QgsProcessingFeedback-like object) used to push progress and log messages
back to the Processing panel.  Pass ``None`` to run without QGIS.

Author:  Phillipe Wernette, PhD  (pwernett@msu.edu)
         Michigan State University — RS&GIS
"""

import math
import os
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import rasterio
import rasterio.shutil as rio_shutil
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.windows import Window, from_bounds as win_from_bounds

# ── Constants ──────────────────────────────────────────────────────────────
NODATA_IN  = -9999.0
NODATA_OUT = -9999.0
TILE_ROWS  = 512
TILE_COLS  = 512
MAX_WORKERS = None          # None → os.cpu_count()

COG_COMPRESS   = "zstd"
COG_ZSTD_LEVEL = 18         # 1–22
COG_PREDICTOR  = 3          # floating-point horizontal differencing
COG_BIGTIFF    = "YES"
COG_OVERVIEW_RESAMPLING = Resampling.average
COG_OVERVIEW_LEVELS     = [2, 4, 8, 16, 32, 64, 128, 256]


# ── Tiny feedback shim so the code works with or without QGIS ─────────────
class _PrintFeedback:
    """Minimal stand-in for QgsProcessingFeedback when running standalone."""
    def pushInfo(self, msg):        print(msg)
    def pushWarning(self, msg):     print(f"WARNING: {msg}")
    def reportError(self, msg, *a): print(f"ERROR: {msg}")
    def setProgress(self, pct):     pass
    def setProgressText(self, msg): print(msg)
    def isCanceled(self):           return False


# ── Raster helpers ────────────────────────────────────────────────────────

def open_raster(path: str) -> rasterio.DatasetReader:
    """Open a raster, auto-resolving common extensions if omitted."""
    candidates = [
        path,
        path + ".tif", path + ".tiff",
        path + ".jp2", path + ".j2k",
        path + ".img",
        path + ".nc",
        path + ".h5", path + ".hdf5",
        path + ".vrt",
        path + ".asc", path + ".grd",
        path + ".dat",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return rasterio.open(c)
            except Exception:
                continue
    raise FileNotFoundError(
        f"Cannot find raster '{path}' (tried .tif/.tiff/.jp2/.img/.nc/.h5/.vrt/.asc/.dat)"
    )


def check_compatible(src1: rasterio.DatasetReader,
                     src2: rasterio.DatasetReader) -> None:
    """Raise ValueError if CRS or pixel size differ."""
    if src1.crs != src2.crs:
        raise ValueError(
            f"CRS mismatch:\n  {src1.name}: {src1.crs}\n  {src2.name}: {src2.crs}"
        )
    ps1 = (src1.transform[0], abs(src1.transform[4]))
    ps2 = (src2.transform[0], abs(src2.transform[4]))
    if not np.allclose(ps1, ps2, rtol=1e-6):
        raise ValueError(
            f"Pixel size mismatch:\n  {src1.name}: {ps1}\n  {src2.name}: {ps2}"
        )


def compute_intersection_bounds(bounds_list: list) -> tuple:
    """Return (minx, miny, maxx, maxy) intersection of all input bounds."""
    minx = max(b[0] for b in bounds_list)
    miny = max(b[1] for b in bounds_list)
    maxx = min(b[2] for b in bounds_list)
    maxy = min(b[3] for b in bounds_list)
    if minx >= maxx or miny >= maxy:
        raise ValueError(
            "Input rasters do not spatially overlap — cannot compute intersection."
        )
    return minx, miny, maxx, maxy


def build_windows(bounds: tuple, pixel_size: float,
                  tile_rows: int = TILE_ROWS, tile_cols: int = TILE_COLS):
    """Yield (minx_tile, miny_tile, Window) tuples tiling *bounds*."""
    minx, miny, maxx, maxy = bounds
    total_cols = int(np.ceil((maxx - minx) / pixel_size))
    total_rows = int(np.ceil((maxy - miny) / pixel_size))
    for row_off in range(0, total_rows, tile_rows):
        actual_rows = min(tile_rows, total_rows - row_off)
        miny_tile   = maxy - (row_off + actual_rows) * pixel_size
        for col_off in range(0, total_cols, tile_cols):
            actual_cols = min(tile_cols, total_cols - col_off)
            minx_tile   = minx + col_off * pixel_size
            yield minx_tile, miny_tile, Window(col_off, row_off, actual_cols, actual_rows)


# ── Core per-pixel maths ─────────────────────────────────────────────────

def _intersection_point(mu_lo, sd_lo, mu_hi, sd_hi):
    """Intersection of two Gaussian PDFs (preserves C++ pow(2,x) formula)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        inner = (
            np.power(2.0, mu_lo - mu_hi)
            + 2.0 * (np.power(2.0, sd_lo) - np.power(2.0, sd_hi))
            * np.log(sd_lo / sd_hi)
        )
        sqrt_term = np.where(inner >= 0, np.sqrt(np.maximum(inner, 0.0)), np.nan)
        num   = mu_hi * np.power(2.0, sd_lo) - sd_hi * (mu_lo * sd_hi + sd_lo + sqrt_term)
        denom = np.power(2.0, sd_lo) - sd_hi
        return np.where(denom != 0, num / denom, np.nan)


def _prob_from_intersection(c, mu_lo, sd_lo, mu_hi, _sd_hi):
    """P(change) via erf integral (matches C++ source exactly)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sqrt2_sd = np.sqrt(2.0) * sd_lo
        verf = np.vectorize(math.erf)
        return (
            1.0
            - 0.5 * np.where(sqrt2_sd != 0, verf((c - mu_lo) / sqrt2_sd), 0.0)
            + 0.5 * np.where(sqrt2_sd != 0, verf((c - mu_hi) / sqrt2_sd), 0.0)
        )


def compute_tile(mu1, sd1, mu2, sd2,
                 nodata_in=NODATA_IN, nodata_out=NODATA_OUT):
    """Vectorised change + probability for one tile."""
    change = np.full(mu1.shape, nodata_out, dtype=np.float32)
    prob   = np.full(mu1.shape, nodata_out, dtype=np.float32)
    valid  = (mu1 > nodata_in) & (mu2 > nodata_in)
    change[valid] = (mu2 - mu1)[valid]

    m1_lt = valid & (mu1 < mu2)
    if m1_lt.any():
        c = _intersection_point(mu1[m1_lt], sd1[m1_lt], mu2[m1_lt], sd2[m1_lt])
        prob[m1_lt] = _prob_from_intersection(c, mu1[m1_lt], sd1[m1_lt],
                                               mu2[m1_lt], sd2[m1_lt])

    m2_lt = valid & (mu2 < mu1)
    if m2_lt.any():
        c = _intersection_point(mu2[m2_lt], sd2[m2_lt], mu1[m2_lt], sd1[m2_lt])
        prob[m2_lt] = _prob_from_intersection(c, mu2[m2_lt], sd2[m2_lt],
                                               mu1[m2_lt], sd1[m2_lt])
    return change, prob


# ── Subprocess worker (must be top-level for pickle) ─────────────────────

def _process_window(args):
    """Read one tile, compute change + probability, return arrays."""
    minx_tile, miny_tile, window, paths, global_errors, pixel_size = args

    maxx_tile = minx_tile + window.width  * pixel_size
    maxy_tile = miny_tile + window.height * pixel_size

    def safe_read(path, minx, miny, maxx, maxy):
        with rasterio.open(path) as ds:
            b = ds.bounds
            if maxx <= b.left or minx >= b.right or maxy <= b.bottom or miny >= b.top:
                nd = ds.nodata if ds.nodata is not None else NODATA_IN
                shape = (int(np.ceil((maxy - miny) / pixel_size)),
                         int(np.ceil((maxx - minx) / pixel_size)))
                return np.full(shape, nd, dtype=np.float32), nd
            lx, ly = max(minx, b.left),   max(miny, b.bottom)
            ux, uy = min(maxx, b.right),  min(maxy, b.top)
            try:
                w   = win_from_bounds(lx, ly, ux, uy, ds.transform)
                dat = ds.read(1, window=w).astype(np.float32)
                nd  = ds.nodata if ds.nodata is not None else NODATA_IN
                return dat, nd
            except Exception:
                nd = ds.nodata if ds.nodata is not None else NODATA_IN
                shape = (int(np.ceil((maxy - miny) / pixel_size)),
                         int(np.ceil((maxx - minx) / pixel_size)))
                return np.full(shape, nd, dtype=np.float32), nd

    mu1, nd1 = safe_read(paths["s1"], minx_tile, miny_tile, maxx_tile, maxy_tile)
    mu2, nd2 = safe_read(paths["s2"], minx_tile, miny_tile, maxx_tile, maxy_tile)
    mu1 = np.where(mu1 <= nd1, NODATA_IN, mu1)
    mu2 = np.where(mu2 <= nd2, NODATA_IN, mu2)

    if global_errors["se1"] is not None:
        sd1 = np.full_like(mu1, global_errors["se1"] / 1.96)
    else:
        e1, _ = safe_read(paths["se1"], minx_tile, miny_tile, maxx_tile, maxy_tile)
        sd1 = np.where(e1 <= NODATA_IN, 0.0, e1) / 1.96

    if global_errors["se2"] is not None:
        sd2 = np.full_like(mu2, global_errors["se2"] / 1.96)
    else:
        e2, _ = safe_read(paths["se2"], minx_tile, miny_tile, maxx_tile, maxy_tile)
        sd2 = np.where(e2 <= NODATA_IN, 0.0, e2) / 1.96

    sd1 = np.maximum(sd1, 1e-10)
    sd2 = np.maximum(sd2, 1e-10)

    change, prob = compute_tile(mu1, sd1, mu2, sd2)
    return window, change, prob


# ── COG output helpers ────────────────────────────────────────────────────

def _temp_profile(ref_src, height, width, transform, dtype=np.float32):
    p = ref_src.profile.copy()
    p.update(
        driver="GTiff", dtype=dtype, count=1, nodata=NODATA_OUT,
        height=height, width=width, transform=transform,
        tiled=True, blockxsize=TILE_COLS, blockysize=TILE_ROWS,
        bigtiff=COG_BIGTIFF, compress="none",
    )
    p.pop("overview_level", None)
    return p


def _cog_profile(ref_src, height, width, transform, dtype=np.float32):
    p = ref_src.profile.copy()
    p.update(
        driver="GTiff", dtype=dtype, count=1, nodata=NODATA_OUT,
        height=height, width=width, transform=transform,
        tiled=True, blockxsize=TILE_COLS, blockysize=TILE_ROWS,
        compress=COG_COMPRESS, zstd_level=COG_ZSTD_LEVEL,
        predictor=COG_PREDICTOR, bigtiff=COG_BIGTIFF,
        copy_src_overviews=True,
    )
    p.pop("overview_level", None)
    return p


def finalize_cog(tmp_path: str, cog_path: str,
                 ref_src, height, width, transform,
                 feedback=None) -> None:
    """Build overviews on tmp_path then copy as a proper COG."""
    fb = feedback or _PrintFeedback()
    with rasterio.open(tmp_path, "r+") as tmp:
        min_dim = min(height, width)
        levels  = [lvl for lvl in COG_OVERVIEW_LEVELS if (min_dim // lvl) >= 1] or [2]
        fb.pushInfo(f"    Building {len(levels)} overview level(s): {levels}")
        tmp.build_overviews(levels, COG_OVERVIEW_RESAMPLING)
        tmp.update_tags(ns="rio_overview", resampling=COG_OVERVIEW_RESAMPLING.name)

    fb.pushInfo(f"    Writing COG: {cog_path}")
    rio_shutil.copy(
        tmp_path, cog_path,
        **_cog_profile(ref_src, height, width, transform),
    )


# ── Public entry point ────────────────────────────────────────────────────

def run_change_detection(
    s1_path: str,
    se1_path: str,
    se1_is_float: bool,
    se1_scalar,
    s2_path: str,
    se2_path: str,
    se2_is_float: bool,
    se2_scalar,
    change_out_path: str,
    prob_out_path: str,
    feedback=None,
) -> None:
    """
    Run the full DEM change detection workflow.

    Parameters
    ----------
    s1_path, s2_path : str
        Paths to the t0 and t1 DEMs (with or without extension).
    se1_path, se2_path : str
        Path to error raster, or string representation of scalar (ignored when
        se*_is_float is True).
    se1_is_float, se2_is_float : bool
        True → use se*_scalar; False → read se*_path as a raster.
    se1_scalar, se2_scalar : float or None
        Global scalar uncertainty (95% CI).  Used only when se*_is_float=True.
    change_out_path, prob_out_path : str
        Destination paths for the two output COG rasters.
    feedback : QgsProcessingFeedback-like, optional
        Progress/log sink.  Pass None for standalone use.
    """
    fb = feedback or _PrintFeedback()

    fb.pushInfo("Opening input rasters …")
    with open_raster(s1_path) as src1, open_raster(s2_path) as src2:

        check_compatible(src1, src2)
        if not se1_is_float:
            with open_raster(se1_path) as sre1:
                check_compatible(src1, sre1)
        if not se2_is_float:
            with open_raster(se2_path) as sre2:
                check_compatible(src1, sre2)

        # Resolved paths (with extension) for subprocess workers
        paths = {
            "s1":  open_raster(s1_path).name,
            "s2":  open_raster(s2_path).name,
            "se1": None if se1_is_float else open_raster(se1_path).name,
            "se2": None if se2_is_float else open_raster(se2_path).name,
        }
        global_errors = {
            "se1": float(se1_scalar) if se1_is_float else None,
            "se2": float(se2_scalar) if se2_is_float else None,
        }

        # Compute intersection extent
        bounds_list = [
            (src1.bounds.left, src1.bounds.bottom, src1.bounds.right, src1.bounds.top),
            (src2.bounds.left, src2.bounds.bottom, src2.bounds.right, src2.bounds.top),
        ]
        if not se1_is_float:
            with open_raster(se1_path) as sr:
                bounds_list.append(
                    (sr.bounds.left, sr.bounds.bottom, sr.bounds.right, sr.bounds.top)
                )
        if not se2_is_float:
            with open_raster(se2_path) as sr:
                bounds_list.append(
                    (sr.bounds.left, sr.bounds.bottom, sr.bounds.right, sr.bounds.top)
                )

        intersect = compute_intersection_bounds(bounds_list)
        pixel_size = abs(src1.transform[0])

        out_height = int(np.ceil((intersect[3] - intersect[1]) / pixel_size))
        out_width  = int(np.ceil((intersect[2] - intersect[0]) / pixel_size))
        out_transform = from_bounds(*intersect, out_width, out_height)

        windows  = list(build_windows(intersect, pixel_size))
        n_tiles  = len(windows)

        fb.pushInfo(
            f"Grid {out_height}×{out_width} px → {n_tiles} tiles "
            f"({TILE_ROWS}×{TILE_COLS} px each)"
        )

        # ── Temp file paths live beside the final outputs ──────────────────
        change_tmp = change_out_path.replace(".tif", "_tmp.tif")
        prob_tmp   = prob_out_path.replace(".tif",   "_tmp.tif")

        # Guard against identical names if caller strips extension differently
        if change_tmp == change_out_path:
            change_tmp = change_out_path + "_tmp"
        if prob_tmp == prob_out_path:
            prob_tmp = prob_out_path + "_tmp"

        tmp_prof = _temp_profile(src1, out_height, out_width, out_transform)

        # ── Pass 1: parallel tile processing ──────────────────────────────
        fb.pushInfo("Pass 1 — processing tiles …")
        fb.setProgressText("Pass 1 of 2: computing change and probability …")

        work_args = [
            (mx, my, win, paths, global_errors, pixel_size)
            for mx, my, win in windows
        ]

        with (
            rasterio.open(change_tmp, "w", **tmp_prof) as dst_change,
            rasterio.open(prob_tmp,   "w", **tmp_prof) as dst_prob,
        ):
            completed = 0
            with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {pool.submit(_process_window, a): a for a in work_args}
                for future in as_completed(futures):
                    if fb.isCanceled():
                        pool.shutdown(wait=False, cancel_futures=True)
                        Path(change_tmp).unlink(missing_ok=True)
                        Path(prob_tmp).unlink(missing_ok=True)
                        raise RuntimeError("Processing cancelled by user.")

                    try:
                        win, change_tile, prob_tile = future.result()
                    except Exception as exc:
                        fb.reportError(f"Tile failed: {exc}")
                        continue

                    dst_change.write(change_tile[np.newaxis], window=win)
                    dst_prob.write(prob_tile[np.newaxis],     window=win)

                    completed += 1
                    pct = int(80 * completed / n_tiles)   # 0–80 % for pass 1
                    fb.setProgress(pct)
                    if completed % max(1, n_tiles // 10) == 0 or completed == n_tiles:
                        fb.pushInfo(
                            f"  {completed}/{n_tiles} tiles ({100*completed/n_tiles:.0f}%)"
                        )

        # ── Pass 2: overviews + COG finalisation ───────────────────────────
        fb.pushInfo("Pass 2 — building overviews and writing COG outputs …")
        fb.setProgressText("Pass 2 of 2: compressing and building overviews …")
        fb.setProgress(82)

        fb.pushInfo("  Change raster:")
        finalize_cog(change_tmp, change_out_path, src1,
                     out_height, out_width, out_transform, fb)
        Path(change_tmp).unlink(missing_ok=True)
        fb.setProgress(91)

        fb.pushInfo("  Probability raster:")
        finalize_cog(prob_tmp, prob_out_path, src1,
                     out_height, out_width, out_transform, fb)
        Path(prob_tmp).unlink(missing_ok=True)
        fb.setProgress(100)

    fb.pushInfo(
        f"\nDone.\n"
        f"  Change raster:      {change_out_path}\n"
        f"  Probability raster: {prob_out_path}\n"
        f"  Format: COG / ZSTD level {COG_ZSTD_LEVEL} / predictor {COG_PREDICTOR} / BigTIFF"
    )
