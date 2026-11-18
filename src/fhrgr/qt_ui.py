from pathlib import Path

from qgis.PyQt.QtGui import QGuiApplication
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.uic import loadUi


def load_ui(widget, filename):
    loadUi(str(Path(__file__).with_name(filename)), widget)


def set_dialog_initial_size(dialog, text_columns=56):
    if not isinstance(dialog, QDialog):
        return

    dialog.ensurePolished()
    font_metrics = dialog.fontMetrics()
    preferred_width = max(
        dialog.width(), font_metrics.horizontalAdvance("M" * text_columns)
    )

    screen = dialog.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        available_width = screen.availableGeometry().width()
        preferred_width = min(preferred_width, int(available_width * 0.9))

    # Let the layout determine the minimum, then widen the initial size.
    dialog.adjustSize()
    dialog.resize(max(dialog.width(), preferred_width), dialog.height())


def configure_message_box(message_box):
    set_dialog_initial_size(message_box, text_columns=64)
