# About

This project is a QGIS 4 plugin for interactive raster georeferencing. The plugin was originally made to replace a workflow where digitizers would use Google Earth to interactively georeference a raster and the tools (move, rotate, scale...) found in that software have been reimplemented. Compared to the standard raster georeferencer tool of QGIS, which needs control points and an export, this plugin allows the visualization of the result immediately, on top of the other layers of the map.

# Install

## From the QGIS plugin registry

In QGIS, open the "Plugins" > "Manage and install plugin" dialog. Install the "Freehand raster georeferencer" plugin.

## From Github

Use the QGIS plugin directory at `src/fhrgr`:

1. Download a ZIP of the repository or clone it using "git clone"
2. Copy the `src/fhrgr` directory directly under your QGIS plugin directory and name the copy `FreehandRasterGeoreferencer` to match the registered plugin package
3. Restart QGIS; the plugin should be listed in the "Plugins" > "Manage and install plugin" dialog

The plugin is QGIS 4-only. QGIS 3 compatibility is not maintained on this branch. A legacy version for QGIS 2 is in the `qgis2` branch.

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


# Development

This repository uses [uv](https://docs.astral.sh/uv/) for local tooling.

```sh
uv sync --frozen
uv run task lint
uv run task format-check
uv run task test
uv run task package
```

Plugin code, ordinary tests, and development scripts live in `src/fhrgr`, `src/tests`, and `src/scripts`.

## QGIS Desktop tests on macOS

With QGIS 4 installed, run `uv run task setup-qgis-tests` from the repository root.
This stages the locked pytest dependencies in the gitignored `.qgis-test-deps/`
directory. Run the setup again after updating the pytest dependencies in `uv.lock`.

- Run `uv run task test` for the full suite, or `uv run pytest -m qgis_desktop -v -rP`
  for the QGIS tests and their output. The launcher uses `/Applications/QGIS4.app`
  by default. Pass `--qgis-app='/Applications/QGIS Preview.app'` to select a
  different QGIS 4 app bundle.
- In VS Code, select `.venv/bin/python` as the interpreter, enable pytest, and
  set `python.testing.pytestArgs` to `["src/tests"]`. To select a different bundle,
  add `"--qgis-app=/Applications/QGIS Preview.app"` as a single entry in that array.

The full QGIS suite runs offscreen at 1× scale. Two separate launcher tests run
the dialog layout check at 1.5× and 2×. Each launch uses a temporary profile and
runs tests from `src/qgis_tests` against the checkout. Use
`uv run pytest -m 'not qgis_desktop'` to run only the tests that work without QGIS.

## Packaging

To set the plugin version, edit `version` under `[project]` in `pyproject.toml`, then run `uv run plugin-version sync` to update `src/fhrgr/metadata.txt`. The `uv run task sync-version` task runs the same command.

The package task uses `qgis-plugin-ci` to create a QGIS plugin ZIP from `src/fhrgr` using the version in `pyproject.toml`. The ZIP is written to the repository root as `fhrgr.<version>.zip` and contains the plugin under `FreehandRasterGeoreferencer/`, matching the existing QGIS registry package. The plugin directory includes the required `LICENSE` file. The `.ui` files are loaded at runtime, so no generated `ui_*.py` files are needed.

## Deploy checklist

Before the first deployment, configure the `QGIS_PLUGIN_TOKEN` repository secret as described below.

For each release:

1. Make sure the code to release is on your local `master` branch.
2. Set `version` under `[project]` in `pyproject.toml`, for example `0.400.0`. Do not include the `v` prefix. Choose a version whose `v<version>` tag does not already exist, and update the changelog in `src/fhrgr/metadata.txt` for that release.
3. Copy the project version into the plugin metadata:
 
   ```sh
   uv run task sync-version
   ```

4. Check the release locally:

   ```sh
   uv run task lint
   uv run task format-check
   uv run task test
   ```

5. Review `git status` and stage all files intended for the release, including new files. Commit the release changes, then push `master`:

   ```sh
   git commit -m "Prepare release 0.400.0"
   git push origin master
   git status
   ```

   The working tree must be clean, with local `master` and `origin/master` pointing to the same commit.

6. Start deployment:

   ```sh
   ./deploy.sh
   ```

    The wrapper reads the version from `pyproject.toml`, creates and pushes an annotated tag such as `v0.400.0`, and watches the release workflow using `~/bin/_deploy/watch_workflow.sh` (use `--nowatch` on machines without the watcher).

    GitHub Actions runs on `v<version>` tags, checks that the tag matches the project version, creates the GitHub release for that tag, and uploads the plugin ZIP to that release and the QGIS registry. The plugin metadata and ZIP filename keep the unprefixed version, such as `0.400.0`.

### Delete the last release before retrying a submission to the QGIS registry

To remove the most recently created GitHub release:

```sh
./last-release-delete.sh
```

### QGIS registry token for GitHub Actions

The release workflow requires a token for uploading plugin versions to the QGIS plugin registry:

1. Sign in to the [QGIS plugin registry](https://plugins.qgis.org/) with an account allowed to manage the plugin. The plugin must already be registered.
2. Open the plugin page and append `tokens/create/` to its URL (`https://plugins.qgis.org/plugins/<package_name>/tokens/create/`). Create a plugin-specific token and copy its value.
3. In this GitHub repository, open **Settings > Secrets and variables > Actions > New repository secret**. Set the name to `QGIS_PLUGIN_TOKEN`, paste the token into **Secret**, and click **Add secret**.

The workflow passes `secrets.QGIS_PLUGIN_TOKEN` to `qgis-plugin-ci` with `--qgis-token`.
