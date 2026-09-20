import configparser
import importlib
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import types
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "fhgr"


def plugin_sources():
    return "\n".join(path.read_text() for path in PLUGIN.glob("*.py"))


def ui_files():
    return sorted(PLUGIN.glob("*.ui"))


def test_utils_helpers_without_qgis(monkeypatch):
    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    core = types.ModuleType("qgis.core")
    qtcore.qDebug = lambda _message: None
    core.QgsProject = object

    monkeypatch.setitem(sys.modules, "qgis", qgis)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "qgis.core", core)
    sys.modules.pop("fhgr.utils", None)

    utils = importlib.import_module("fhgr.utils")

    assert utils.image_format("scan.tiff") == "tif"
    assert utils.image_format("scan.tifF") == "tif"
    assert utils.image_format("scan.PNG") == "png"
    assert utils.tryfloat("1.25") == 1.25
    assert utils.tryfloat("not-a-number") is None


def test_metadata_targets_qgis4_only():
    metadata = configparser.ConfigParser()
    metadata.read(PLUGIN / "metadata.txt")
    general = metadata["general"]

    assert general["version"] == "0.9.0"
    assert general["qgisMinimumVersion"] == "4.0"
    assert general["qgisMaximumVersion"] == "4.99"
    assert general["icon"] == "icons/icon.png"
    assert "supportsQt6" not in general


def test_no_legacy_qgis3_qt5_artifacts_remain():
    source = plugin_sources()

    forbidden_literals = [
        "PyQt5",
        "PyQt6",
        "resources_rc",
        "exec_(",
        "QgsWkbTypes",
        "QgsMapLayer.PluginLayer",
        "Qgis.Info",
        "Qgis.Warning",
        "Qgis.Critical",
        "QImageReader",
        "previewAsImage",
    ]
    for literal in forbidden_literals:
        assert literal not in source

    assert not re.search(r"from\s+\.\s*ui_", source)
    assert not re.search(r"import\s+\.\s*ui_", source)
    assert not re.search(r"def\s+metadata\s*\(", source)


def test_properties_dialog_uses_qt6_tab_stop_api():
    ui = (PLUGIN / "propertiesdialog.ui").read_text()

    assert "tabStopWidth" not in ui
    assert "tabStopDistance" in ui
    assert "setTabStopDistance" not in (PLUGIN / "propertiesdialog.py").read_text()


def test_plugin_package_contains_runtime_assets():
    required = [
        PLUGIN / "__init__.py",
        PLUGIN / "metadata.txt",
        PLUGIN / "freehandrastergeoreferencerdialog.ui",
        PLUGIN / "exportgeorefrasterdialog.ui",
        PLUGIN / "loaderrordialog.ui",
        PLUGIN / "propertiesdialog.ui",
        PLUGIN / "icons" / "icon.png",
    ]

    for path in required:
        assert path.exists(), path


def test_ui_child_widgets_do_not_use_fixed_geometry():
    for ui_path in ui_files():
        root = ET.parse(ui_path).getroot()
        top_level_widget = root.find("widget")
        assert top_level_widget is not None, ui_path

        for widget in top_level_widget.findall(".//widget"):
            geometry = widget.find("./property[@name='geometry']")
            assert geometry is None, (
                f"{ui_path.name}: widget {widget.attrib.get('name')} "
                "uses fixed geometry instead of a layout"
            )


def test_plugin_dialogs_use_layouts_and_default_font_sizes():
    dialog_files = [
        PLUGIN / "freehandrastergeoreferencerdialog.ui",
        PLUGIN / "exportgeorefrasterdialog.ui",
        PLUGIN / "loaderrordialog.ui",
    ]

    for ui_path in dialog_files:
        root = ET.parse(ui_path).getroot()
        top_level_widget = root.find("widget")

        assert top_level_widget is not None, ui_path
        assert top_level_widget.find("layout") is not None, ui_path
        assert "<pointsize>" not in ui_path.read_text()


def test_qgis_dialogs_have_sane_offscreen_size_hints():
    pytest.importorskip("qgis.PyQt.QtWidgets")

    code = r"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.PyQt.QtWidgets import QApplication, QWidget

from fhgr.exportgeorefrasterdialog import ExportGeorefRasterDialog
from fhgr.freehandrastergeoreferencerdialog import FreehandRasterGeoreferencerDialog
from fhgr.loaderrordialog import LoadErrorDialog


app = QApplication.instance() or QApplication([])
parent = QWidget()

dialogs = [
    (
        LoadErrorDialog(
            "C:/Users/loren/Giant Files/QGIS files/Projects - WLR/"
            "QGIS only/WLR fresh 220823/E GH Grading snip.PNG",
            parent=parent,
        ),
        ("lblError", "lineEditImagePath", "pushButtonBrowse"),
    ),
    (
        FreehandRasterGeoreferencerDialog(parent=parent),
        (
            "lineEditImagePath",
            "pushButtonBrowse",
            "toolButtonAdvanced",
            "pushButtonAdd",
            "pushButtonCancel",
        ),
    ),
    (
        ExportGeorefRasterDialog(parent=parent),
        (
            "lineEditImagePath",
            "pushButtonBrowse",
            "checkBoxRotationMode",
            "checkBoxOnlyWorldFile",
        ),
    ),
]

for dialog, names in dialogs:
    dialog.ensurePolished()
    dialog.adjustSize()
    assert dialog.sizeHint().width() > 0
    assert dialog.sizeHint().height() > 0
    for name in names:
        widget = getattr(dialog, name)
        assert widget.sizeHint().width() > 0, name
        assert widget.sizeHint().height() > 0, name

assert dialogs[0][0].lblError.wordWrap()
"""

    for scale_factor in ("1", "1.5", "2"):
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["QT_SCALE_FACTOR"] = scale_factor
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            check=False,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
