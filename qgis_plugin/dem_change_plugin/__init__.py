"""
DEM Change Detection QGIS Plugin
---------------------------------
Registers the Processing provider on plugin load.
"""

def classFactory(iface):
    from .plugin import DEMChangePlugin
    return DEMChangePlugin(iface)
