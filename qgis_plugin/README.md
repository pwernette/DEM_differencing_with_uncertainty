# DEM Change Detection — QGIS Plugin

**Citation:** Wernette, P. and J. Lehner (2026) pwernette/DEM_differencing_with_uncertainty: DEM Change with Uncertainty (1.01). Zenodo. [![DOI](../assets/zenodo.20754255.svg)](https://doi.org/10.5281/zenodo.20754255)

This directory contains a QGIS Processing plugin that exposes the probabilistic DEM change detection algorithm directly inside QGIS. The underlying computation is identical to the Python command-line implementation; this plugin adds a graphical interface and integrates with the QGIS layer panel.

> Wernette, P., J. Lehner, and C. Houser. (2020) What change is 'real'? A probabilistic approach to accounting for uncertainty in environmental change analysis. *Geomorphology*, 355, 107083. http://doi.org/10.1016/j.geomorph.2020.107083.

---

## Compatibility

| Requirement | Version |
|-------------|---------|
| QGIS | 3.16 – 3.x |
| Python | ≥ 3.10 (bundled with QGIS) |
| NumPy | ≥ 1.20 |
| rasterio | ≥ 1.3 |

---

## Installation

### Option 1: Install from ZIP (Recommended)

1. In QGIS, open **Plugins → Manage and Install Plugins…**
2. Click the **Install from ZIP** tab.
3. Browse to `dem_change_plugin.zip` in this directory.
4. Click **Install Plugin**.

### Option 2: Install Manually

1. Locate your QGIS user plugins folder:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS / Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
2. Copy the `dem_change_plugin/` folder into that directory.
3. Restart QGIS.
4. Enable the plugin under **Plugins → Manage and Install Plugins…**.

### Verify Installation

After enabling the plugin, the algorithm appears in the **Processing Toolbox** under:

```
DEM Analysis → Probabilistic DEM Change Detection
```

---

## Usage

1. Open the **Processing Toolbox** (**Processing → Toolbox** or `Ctrl+Alt+T`).
2. Navigate to **DEM Analysis → Probabilistic DEM Change Detection**.
3. Double-click the algorithm to open the parameter dialog.

### Input Parameters

| Parameter | Description |
|-----------|-------------|
| **DEM at Time 1 (t0)** | Raster layer for the earlier DEM epoch. |
| **Uncertainty type for DEM t0** | Choose *Raster error surface* or *Global scalar value*. |
| **Error surface for DEM t0** | Spatially variable uncertainty raster (95% CI); required when type = Raster. |
| **Global uncertainty for DEM t0** | Single uncertainty value in the same units as the DEM (95% CI); required when type = Scalar. Default: 0.10. |
| **DEM at Time 2 (t1)** | Raster layer for the later DEM epoch. |
| **Uncertainty type for DEM t1** | Choose *Raster error surface* or *Global scalar value*. |
| **Error surface for DEM t1** | Spatially variable uncertainty raster (95% CI); required when type = Raster. |
| **Global uncertainty for DEM t1** | Single uncertainty value (95% CI); required when type = Scalar. Default: 0.10. |
| **Output: Elevation Change (DoD)** | Destination path for the difference-of-DEMs raster. |
| **Output: Probability of Significant Change** | Destination path for the per-pixel probability raster. |

> **Note:** Error values are interpreted as 95% confidence intervals (±1.96σ) and converted internally to 1-sigma standard deviations before computation.

### Output Files

Both outputs are Cloud-Optimized GeoTIFFs with ZSTD compression:

| Output | Description | Range |
|--------|-------------|-------|
| `*_change.tif` | Elevation difference (mu2 − mu1), same units as input DEMs | −∞ to +∞ |
| `*_probability.tif` | Probability of significant change at each pixel | 0.0 to 1.0 |

**Interpreting the probability raster:**
- `0.0` — high confidence that **no change** occurred
- `0.5` — maximum uncertainty
- `1.0` — high confidence that **real change** occurred

Outputs are automatically added to the QGIS layer panel on completion.

---

## Algorithm Overview

The plugin delegates all computation to `dem_change_core.py`. For each pixel in the intersection of the two input rasters:

1. **Difference of DEMs (DoD):** `change = mu2 − mu1`
2. **PDF intersection:** finds the crossing point `c` of the two Gaussian error distributions
3. **Probability:** integrates the area under the lower PDF beyond `c` using the analytical error function — no Monte Carlo simulation required

Processing is tile-based (512 × 512 px) and parallelised across available CPU cores.

---

## References

> Wernette, P., J. Lehner, and C. Houser. (2020) What change is 'real'? A probabilistic approach to accounting for uncertainty in environmental change analysis. *Geomorphology*, 355, 107083. http://doi.org/10.1016/j.geomorph.2020.107083.

---

## Contact

Phillipe Wernette, PhD [pwernett@msu.edu]()
