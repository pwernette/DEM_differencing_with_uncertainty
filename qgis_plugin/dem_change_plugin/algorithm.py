"""
algorithm.py  —  QgsProcessingAlgorithm wrapping the DEM change detection logic.

All computation is delegated to dem_change_core.py (the ported science code).
This file handles only the QGIS Processing API: parameter definitions,
input validation, progress reporting, and loading outputs back into QGIS.
"""

import os
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterEnum,
    QgsProcessingOutputRasterLayer,
    QgsProcessingException,
    QgsRasterLayer,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon


class DEMChangeAlgorithm(QgsProcessingAlgorithm):
    """
    Probabilistic DEM change detection with spatially variable uncertainty.

    Computes:
      • Difference of DEMs (DoD): elevation change (mu2 − mu1)
      • Probability of significant change [0, 1] based on analytical
        intersection of the two Gaussian error distributions

    Both outputs are Cloud-Optimized GeoTIFFs (ZSTD level 18, predictor 3,
    BigTIFF, embedded power-of-2 overviews).
    """

    # ── Parameter names ────────────────────────────────────────────────────
    INPUT_DEM1       = "INPUT_DEM1"
    ERROR1_RASTER    = "ERROR1_RASTER"
    ERROR1_SCALAR    = "ERROR1_SCALAR"
    ERROR1_MODE      = "ERROR1_MODE"

    INPUT_DEM2       = "INPUT_DEM2"
    ERROR2_RASTER    = "ERROR2_RASTER"
    ERROR2_SCALAR    = "ERROR2_SCALAR"
    ERROR2_MODE      = "ERROR2_MODE"

    OUTPUT_CHANGE    = "OUTPUT_CHANGE"
    OUTPUT_PROB      = "OUTPUT_PROB"

    # ── Algorithm identity ─────────────────────────────────────────────────
    def name(self):
        return "dem_change_detection"

    def displayName(self):
        return self.tr("Probabilistic DEM Change Detection")

    def group(self):
        return self.tr("DEM Analysis")

    def groupId(self):
        return "dem_analysis"

    def shortDescription(self):
        return self.tr(
            "Compute elevation change and probability of significant change "
            "between two DEMs, accounting for spatially variable uncertainty."
        )

    def helpUrl(self):
        return "https://github.com/pwernette/DEM_differencing_with_uncertainty"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        return QIcon(icon_path) if os.path.exists(icon_path) else super().icon()

    def createInstance(self):
        return DEMChangeAlgorithm()

    def tr(self, string):
        return QCoreApplication.translate("DEMChangeAlgorithm", string)

    # ── Parameter definitions ──────────────────────────────────────────────
    def initAlgorithm(self, config=None):

        # ── DEM at t0 ──────────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_DEM1,
                self.tr("DEM at Time 1 (t0)"),
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.ERROR1_MODE,
                self.tr("Uncertainty type for DEM t0"),
                options=[
                    self.tr("Raster error surface"),
                    self.tr("Global scalar value"),
                ],
                defaultValue=1,
            )
        )

        p_e1r = QgsProcessingParameterRasterLayer(
            self.ERROR1_RASTER,
            self.tr("Error surface for DEM t0 (raster, 95% CI)"),
            optional=True,
        )
        p_e1r.setHelp(
            self.tr(
                "Spatially variable uncertainty raster for the first DEM, "
                "expressed as a 95% confidence interval (±1.96σ). "
                "Required when 'Uncertainty type' is set to 'Raster error surface'."
            )
        )
        self.addParameter(p_e1r)

        p_e1s = QgsProcessingParameterNumber(
            self.ERROR1_SCALAR,
            self.tr("Global uncertainty for DEM t0 (scalar, 95% CI)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.10,
            minValue=0.0001,
            optional=True,
        )
        p_e1s.setHelp(
            self.tr(
                "Single uncertainty value applied uniformly to the first DEM, "
                "expressed as a 95% confidence interval (±1.96σ). "
                "Required when 'Uncertainty type' is set to 'Global scalar value'."
            )
        )
        self.addParameter(p_e1s)

        # ── DEM at t1 ──────────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_DEM2,
                self.tr("DEM at Time 2 (t1)"),
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.ERROR2_MODE,
                self.tr("Uncertainty type for DEM t1"),
                options=[
                    self.tr("Raster error surface"),
                    self.tr("Global scalar value"),
                ],
                defaultValue=1,
            )
        )

        p_e2r = QgsProcessingParameterRasterLayer(
            self.ERROR2_RASTER,
            self.tr("Error surface for DEM t1 (raster, 95% CI)"),
            optional=True,
        )
        p_e2r.setHelp(
            self.tr(
                "Spatially variable uncertainty raster for the second DEM, "
                "expressed as a 95% confidence interval (±1.96σ)."
            )
        )
        self.addParameter(p_e2r)

        p_e2s = QgsProcessingParameterNumber(
            self.ERROR2_SCALAR,
            self.tr("Global uncertainty for DEM t1 (scalar, 95% CI)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.10,
            minValue=0.0001,
            optional=True,
        )
        self.addParameter(p_e2s)

        # ── Outputs ────────────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_CHANGE,
                self.tr("Output: Elevation Change (DoD)"),
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT_PROB,
                self.tr("Output: Probability of Significant Change"),
            )
        )

    # ── Validation ─────────────────────────────────────────────────────────
    def checkParameterValues(self, parameters, context):
        """Validate that the correct error input is supplied for each mode."""
        errors = []

        e1_mode = self.parameterAsEnum(parameters, self.ERROR1_MODE, context)
        if e1_mode == 0:  # raster
            lyr = self.parameterAsRasterLayer(parameters, self.ERROR1_RASTER, context)
            if lyr is None:
                errors.append(
                    self.tr(
                        "An error raster must be supplied for DEM t0 "
                        "when 'Raster error surface' mode is selected."
                    )
                )

        e2_mode = self.parameterAsEnum(parameters, self.ERROR2_MODE, context)
        if e2_mode == 0:  # raster
            lyr = self.parameterAsRasterLayer(parameters, self.ERROR2_RASTER, context)
            if lyr is None:
                errors.append(
                    self.tr(
                        "An error raster must be supplied for DEM t1 "
                        "when 'Raster error surface' mode is selected."
                    )
                )

        if errors:
            return False, "\n".join(errors)
        return super().checkParameterValues(parameters, context)

    # ── Execution ──────────────────────────────────────────────────────────
    def processAlgorithm(self, parameters, context, feedback):
        """
        Main entry point called by QGIS Processing.

        Resolves parameters, delegates computation to dem_change_core,
        and returns output paths for QGIS to load.
        """
        # ── Resolve DEM paths ───────────────────────────────────────────────
        dem1_layer = self.parameterAsRasterLayer(parameters, self.INPUT_DEM1, context)
        dem2_layer = self.parameterAsRasterLayer(parameters, self.INPUT_DEM2, context)

        if dem1_layer is None or not dem1_layer.isValid():
            raise QgsProcessingException(self.tr("Invalid DEM t0 layer."))
        if dem2_layer is None or not dem2_layer.isValid():
            raise QgsProcessingException(self.tr("Invalid DEM t1 layer."))

        s1_path = dem1_layer.source()
        s2_path = dem2_layer.source()

        # ── Resolve error inputs ────────────────────────────────────────────
        e1_mode = self.parameterAsEnum(parameters, self.ERROR1_MODE, context)
        if e1_mode == 0:
            lyr = self.parameterAsRasterLayer(parameters, self.ERROR1_RASTER, context)
            se1 = lyr.source()
            se1_is_float = False
            se1_scalar = None
        else:
            se1_scalar = self.parameterAsDouble(parameters, self.ERROR1_SCALAR, context)
            se1 = str(se1_scalar)
            se1_is_float = True

        e2_mode = self.parameterAsEnum(parameters, self.ERROR2_MODE, context)
        if e2_mode == 0:
            lyr = self.parameterAsRasterLayer(parameters, self.ERROR2_RASTER, context)
            se2 = lyr.source()
            se2_is_float = False
            se2_scalar = None
        else:
            se2_scalar = self.parameterAsDouble(parameters, self.ERROR2_SCALAR, context)
            se2 = str(se2_scalar)
            se2_is_float = True

        # ── Resolve output paths ────────────────────────────────────────────
        change_path = self.parameterAsOutputLayer(parameters, self.OUTPUT_CHANGE, context)
        prob_path   = self.parameterAsOutputLayer(parameters, self.OUTPUT_PROB,   context)

        # ── Run computation ─────────────────────────────────────────────────
        feedback.setProgressText(self.tr("Initialising DEM change detection …"))
        feedback.setProgress(0)

        try:
            from .dem_change_core import run_change_detection
            run_change_detection(
                s1_path=s1_path,
                se1_path=se1,
                se1_is_float=se1_is_float,
                se1_scalar=se1_scalar,
                s2_path=s2_path,
                se2_path=se2,
                se2_is_float=se2_is_float,
                se2_scalar=se2_scalar,
                change_out_path=change_path,
                prob_out_path=prob_path,
                feedback=feedback,
            )
        except Exception as exc:
            raise QgsProcessingException(str(exc))

        if feedback.isCanceled():
            raise QgsProcessingException(self.tr("Processing was cancelled."))

        feedback.setProgress(100)

        return {
            self.OUTPUT_CHANGE: change_path,
            self.OUTPUT_PROB:   prob_path,
        }
