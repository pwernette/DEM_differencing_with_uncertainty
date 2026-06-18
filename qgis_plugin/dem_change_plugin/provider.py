"""
provider.py  —  QGIS Processing provider
"""

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon
import os


class DEMChangeProvider(QgsProcessingProvider):

    def id(self):
        return "demchange"

    def name(self):
        return "DEM Change Detection"

    def longName(self):
        return "DEM Change Detection (Probabilistic)"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        return QIcon(icon_path) if os.path.exists(icon_path) else super().icon()

    def loadAlgorithms(self):
        from .algorithm import DEMChangeAlgorithm
        self.addAlgorithm(DEMChangeAlgorithm())

    def supportedOutputRasterLayerExtensions(self):
        return ["tif"]
