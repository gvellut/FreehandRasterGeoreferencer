# About

This project is a QGIS 4 plugin for interactive raster georeferencing. The plugin was originally made to replace a workflow where digitizers would use Google Earth to interactively georeference a raster and the tools (move, rotate, scale...) found in that software have been reimplemented. Compared to the standard raster georeferencer tool of QGIS, which needs control points and an export, this plugin allows the visualization of the result immediately, on top of the other layers of the map.

# Install

## From the QGIS plugin registry

In QGIS, open the "Plugins" > "Manage and install plugin" dialog. Install the "Freehand raster georeferencer" plugin.

## From Github

Use the QGIS plugin directory named `fhrgr`:

1. Download a ZIP of the repository or clone it using "git clone"
2. Copy the `fhrgr` directory directly under your QGIS plugin directory
3. Restart QGIS; the plugin should be listed in the "Plugins" > "Manage and install plugin" dialog

The plugin is QGIS 4-only. QGIS 3 compatibility is not maintained on this branch. A legacy version for QGIS 2 is in the `qgis2` branch.

# Development

This repository uses [uv](https://docs.astral.sh/uv/) for local tooling.

```sh
uv sync --frozen
uv run task lint
uv run task format-check
uv run task test
uv run task package
```

The package task uses `qgis-plugin-ci` and creates a QGIS plugin ZIP from the `fhrgr` directory. The `.ui` files are loaded at runtime, so no generated `ui_*.py` files are needed.

# Documentation

See http://gvellut.github.io/FreehandRasterGeoreferencer/

# Issues

Report issues at https://github.com/gvellut/FreehandRasterGeoreferencer/issues

# Limitations

- The plugin uses GDAL from the QGIS runtime to read rasters for display. PNG, JPEG, TIFF, PDF, and other raster formats can be loaded when the local QGIS GDAL build includes the matching driver, including formats such as ECW in distributions that ship that support. Very large rasters should still be avoided because the plugin keeps a display image in memory for interactive painting.
- This georeferencer only supports affine transformations (without shearing) and not the full set of transformation algorithms (including rubbersheeting) the standard QGIS raster georeferencer provides
- There is limited support for changing CRS: If the CRS of the map changes, you will have to adjust georeferencing of the layer in the new CRS.
- The raster layer added by this plugin does not have all the capabilities of a normal QGIS raster layer: It is limited to visualization and modification using the provided tools. However, a normal QGIS raster file, along with georerencing information, can be easily exported by the plugin and can be reloaded using the standard "Add Raster" functionality.
- The display renderer uses deterministic conversion rules rather than the full QGIS raster renderer. Non-Byte data is rescaled to 8-bit for display, color tables and alpha bands are interpreted where present, and extra bands may be ignored with a warning.
    - If a pixel transformation is performed, the plugin shows a raster-display warning when the raster is opened. When exporting the georeferencing, unless you are fine with the pixel transformation, be sure to check the "Only export world file" in the dialog, then choose the original raster file: In that case, no image data will be exported, just the georeferencing (including rotation).
- It is also possible to perform the pixel transformation yourself, before opening the raster with the plugin. For example, if you have a 10-band raster with band 5, 3, 6 as RGB, you can use GDAL to export a version of the raster with those bands in the correct order. Make sure the dimensions (width, length) of the raster  stay the same though. Then use that version of the raster for georeferencing with the plugin. Finally, export only the world file and select the original raster. The original raster will then have a world file.
