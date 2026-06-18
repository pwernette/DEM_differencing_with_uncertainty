"""
plugin.py  —  QGIS plugin entry point
"""

from qgis.core import QgsApplication
from .provider import DEMChangeProvider


class DEMChangePlugin:
    """Minimal plugin class: just registers / deregisters the Processing provider."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        self.provider = DEMChangeProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
