# Proposal: Organization, Correctness, GDAL Raster Reading, and HiDPI Dialogs

## Summary

This plugin should be organized around a small QGIS-facing shell and testable
core modules. The highest-value correctness change is to stop using Qt image
readers for raster input and instead use GDAL from the QGIS runtime for all
raster loading.

This proposal targets QGIS 4 only. It does not preserve QGIS 3 compatibility.

## Current Problems

- Raster loading is inconsistent:
  - most image formats are read with `QImageReader`;
  - PDFs are read through `QgsRasterLayer.previewAsImage`;
  - TIFFs receive partial GDAL preprocessing only when Qt cannot display them
    well.
- `FreehandRasterGeoreferencerLayer` mixes QGIS layer behavior, raster loading,
  transform math, canvas rendering, project persistence, CRS handling, and user
  dialogs.
- Several correctness-sensitive calculations are hard to test outside QGIS:
  world-file coefficients, geotransform import, corner coordinates, CRS
  reprojection behavior, undo state, and image data conversion.
- The plugin still stores display pixels as a `QImage`, which is acceptable for
  painting, but the creation of that `QImage` should be driven by GDAL data and
  explicit conversion rules, not by Qt's file readers.
- Missing-file recovery is confusing: plugin layers appear in the project layer
  tree with `source=""` and provider `FreehandRasterGeoreferencerLayerProvider`,
  while the actual raster path is stored later as the custom property
  `filepath`. That is technically how plugin layers are persisted today, but it
  makes project-file diagnosis hard and contributes to user confusion when paths
  break after moving a project.


## Target Architecture

- Keep `fhrgr/` as the plugin package.
- Split code into these boundaries:
  - `qgis_plugin.py` or current `freehandrastergeoreferencer.py`: QGIS actions,
    menus, toolbar, map-tool wiring.
  - `layer.py`: QGIS `QgsPluginLayer` integration only.
  - `raster_io.py`: GDAL-backed raster opening, display conversion, geotransform
    and CRS extraction.
  - `transform.py`: pure geometry and affine/world-file math.
  - `export.py`: export workflow and world-file/aux XML writing.
  - `dialogs/` or existing dialog modules: UI behavior only.
  - `qt_image.py`: narrow conversion from GDAL/numpy display buffers to `QImage`.
- Use dataclasses for non-QGIS state where possible:
  - `RasterDisplayImage`: `qimage`, `width`, `height`, `source_path`,
    `was_rescaled`, `warnings`.
  - `RasterGeoreference`: center, rotation, x/y scale, CRS WKT, raw geotransform.
  - `WorldFileTransform`: `a`, `d`, `b`, `e`, `c`, `f`.

## GDAL Raster Reading Plan

1. Introduce `raster_io.py` with a single public entry point:
   `load_raster_for_display(path) -> RasterDisplayImage`.
2. Use `osgeo.gdal` from the QGIS Python environment:
   - open with `gdal.OpenEx(path, gdal.OF_RASTER)`;
   - fail with clear messages when GDAL cannot open the file;
   - read size, band count, data type, color interpretation, nodata, alpha, and
     geotransform.
3. Convert GDAL bands to a display buffer explicitly:
   - 1 band: grayscale, respecting color tables where present;
   - 2 bands: grayscale plus alpha when the second band is alpha, otherwise
     warn and use the first band;
   - 3 bands: RGB;
   - 4+ bands: RGBA when alpha exists, otherwise first RGB-like bands by color
     interpretation or first three bands with a warning.
4. Normalize non-Byte data for display using deterministic rules:
   - preserve Byte values directly;
   - for UInt16/Float/etc., scale to 8-bit from valid min/max or GDAL
     statistics;
   - ignore nodata in min/max when possible;
   - return a warning when display pixels were rescaled.
5. Convert the final numpy buffer to `QImage` in one small adapter function.
   Keep ownership of the backing buffer explicit so the `QImage` remains valid.
6. Replace current `QImageReader` and `QgsRasterLayer.previewAsImage` paths in
   `FreehandRasterGeoreferencerLayer.initializeLayer()` and `replaceImage()`.
7. Keep export behavior initially compatible: export from the display `QImage`
   unless "only world file" is selected. A later improvement can use GDAL for
   transformed raster output too.


## Testability Plan

- Keep tests runnable without launching QGIS.
- Add pure tests for:
  - image format/path helpers;
  - transform/corner coordinate calculations;
  - geotransform-to-plugin-transform conversion;
  - world-file coefficient generation;
  - display scaling rules for GDAL arrays;
  - metadata invariants and QGIS 4 API guardrails.
- Add optional GDAL tests:
  - skip when `osgeo.gdal` is unavailable;
  - create tiny in-memory or temporary rasters for Byte, UInt16, RGB, RGBA,
    nodata, and color-table cases.
- Add optional Qt tests:
  - skip when `qgis.PyQt` is unavailable;
  - validate `QImage` dimensions, format, and backing-buffer lifetime;
  - validate dialog layout behavior offscreen.
- Avoid importing QGIS core modules in pure modules. QGIS-specific adapters can
  remain thin and covered by static or optional integration tests.

## Correctness Improvements

- Preserve the recent fix that avoids overriding `QgsMapLayer.metadata()`;
  plugin-specific text should remain `freehand_metadata()` or equivalent.
- Make plugin layer path persistence easier to reason about:
  - keep the canonical image path in a named custom property;
  - expose the resolved absolute path and stored project-relative path in layer
    properties;
  - document why layer-tree `source=""` is expected for this plugin layer;
  - consider whether the dummy data provider URI can return a useful
    diagnostic source string without breaking QGIS plugin-layer behavior.
- Make raster-display warnings explicit and user-facing:
  - band selection changed;
  - datatype rescaled;
  - nodata/alpha interpreted;
  - georeferencing CRS differs from map CRS.
- Treat georeferencing as data:
  - isolate affine math in pure functions;
  - test default geotransform detection;
  - test rotated/scaled world-file coefficients.
- Fail safely:
  - no partially initialized layer after raster load failure;
  - no fall-through from a cancelled missing-file recovery dialog into raster
    loading;
  - no silent division by zero when data min equals max;
  - clear errors for unsupported or unreadable rasters.

- Improve missing-file recovery UX:
   - show the missing path in a selectable, wrapping text field;
   - show the layer title separately from the file path;
   - make the replacement path chooser clearly tied to that missing layer;
   - validate that replacing a file updates only that plugin layer;
   - use an error message when the selected file does not match expected image
     dimensions, unless the user explicitly chooses to replace with a different
     image.


## Phased Implementation


2. Pure transform extraction
   - Move coordinate and world-file math into `transform.py`.
   - Add tests before changing raster loading.

3. Missing/relocated image recovery
   - Make missing source images a first-class recoverable state.
   - Stop initialization immediately when the user cancels recovery.
   - Add tests for project reload with missing files, cancellation, and
     replacement with same-size and different-size rasters.


4. GDAL display reader
   - Implement `raster_io.py` and `qt_image.py`.
   - Test with tiny GDAL-created rasters.
   - Replace `QImageReader` and PDF preview paths.

5. Layer simplification
   - Make `FreehandRasterGeoreferencerLayer` delegate raster loading and
     transform calculations.
   - Keep QGIS API code thin.

6. Export follow-up
   - Keep current export behavior initially.
   - Consider GDAL-backed transformed export in a separate change once display
     loading is stable.

## Acceptance Criteria

- No direct `QImageReader` raster-loading path remains.
- GDAL handles PNG, JPEG, TIFF, PDF, other raster types like ECW where the QGIS GDAL build supports them.
- Replacing one missing raster cannot silently update or reposition another
  layer.
- Opening a project with missing linked images does not crash or block unrelated
  layers from loading.
- Cancelling missing-image recovery leaves a safe invalid/recoverable layer and
  does not attempt to read or render the missing raster.
- Layer properties clearly show stored path, resolved path, and whether the file
  currently exists.
- Core transform and raster conversion tests run without QGIS.
- Optional GDAL/Qt tests skip cleanly when dependencies are unavailable.
- `uv run task lint`, `uv run task format-check`, `uv run task test`, and
  package verification pass.
