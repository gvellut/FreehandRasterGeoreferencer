import os

import pytest
from qgis.PyQt.QtWidgets import QWidget

from fhrgr.exportgeorefrasterdialog import ExportGeorefRasterDialog
from fhrgr.freehandrastergeoreferencerdialog import FreehandRasterGeoreferencerDialog
from fhrgr.loaderrordialog import LoadErrorDialog


def test_qgis_dialogs_have_sane_offscreen_size_hints():
    parent = QWidget()
    assert parent.devicePixelRatioF() == pytest.approx(
        float(os.environ["QT_SCALE_FACTOR"])
    )
    load_error = LoadErrorDialog(
        "C:/Users/loren/Giant Files/QGIS files/Projects - WLR/"
        "WLR fresh 220823/E GH Grading snip.PNG",
        parent=parent,
    )
    dialogs = (
        (load_error, ("lblError", "lineEditImagePath", "pushButtonBrowse")),
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
    )

    try:
        for dialog, names in dialogs:
            dialog.ensurePolished()
            dialog.adjustSize()
            assert dialog.sizeHint().width() > 0
            assert dialog.sizeHint().height() > 0
            for name in names:
                widget = getattr(dialog, name)
                assert widget.sizeHint().width() > 0, name
                assert widget.sizeHint().height() > 0, name
        assert load_error.lblError.wordWrap()
    finally:
        load_error.reject()
        parent.deleteLater()
