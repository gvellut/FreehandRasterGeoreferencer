# AGENTS.md

## Project

This project is a QGIS 4 plugin for interactive raster georeferencing. 

The plugin package lives in `fhrgr/`; keep plugin code, `metadata.txt`, `.ui` files, and icons there.

## Commands

- Install tooling: `uv sync --frozen`
- Lint: `uv run task lint`
- Format check: `uv run task format-check`
- Tests: `uv run task test`
- Package: `uv run task package`

`qgis-plugin-ci` packages from Git-tracked files. If `fhrgr/` is new or
unstaged, package verification may need a temporary clean Git repo.

## QGIS 4 Rules

- Do not maintain QGIS 3 or Qt 5 compatibility.
- Use `qgis.PyQt`, not direct `PyQt5` or `PyQt6` imports.
- Use Qt 6 scoped enums, for example `Qt.FocusPolicy.ClickFocus`,
  `Qt.MouseButton.LeftButton`, `Qt.KeyboardModifier.ControlModifier`,
  `Qgis.MessageLevel.Warning`, and `Qgis.GeometryType.Line`.
- Use `exec()`, not `exec_()`.
- Use `event.position().toPoint()` instead of `event.pos()` for map mouse events.
- Do not add generated `ui_*.py` or `resources_rc.py`; load `.ui` files at
  runtime with `qgis.PyQt.uic.loadUi`.
- Do not define a string-returning `metadata()` method on plugin layers; QGIS
  expects `QgsMapLayer.metadata()` to return `QgsLayerMetadata`.

## HiDPI UI Rules

- Keep `.ui` files layout-based so dialogs scale correctly on HiDPI displays.
- Do not use fixed child-widget `geometry` blocks; top-level dialog geometry is
  only an initial designer hint.
- Prefer Qt layouts such as `QVBoxLayout`, `QGridLayout`, `QFormLayout`, and
  `QDialogButtonBox`.
- Use expanding line edits for file paths and make long explanatory text wrap.
- Avoid hard-coded point sizes in `.ui` files; use the platform/application font
  unless there is a strong reason otherwise.

## Notes

- The active Ruff config is `ruff.toml`; keep `pyproject.toml` aligned with it.
- Keep `.prompts/` untouched unless explicitly asked.

## Considerations

This is not a library, but a self-contained program. Do no maintain code compatibility between versions. Do not redirect code so the interface is maintained. Interface does not need to be maintained. There is no need for "compatiblity shims".

For internal methods / variables, use snake_case. Only use camelCase for the implementations of QGIS-provided interfaces (if this is what it uses).