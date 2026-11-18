from pathlib import Path

from qgis.PyQt.QtGui import QGuiApplication
from qgis.PyQt.QtWidgets import QDialog, QLayout
from qgis.PyQt.uic import loadUi


def load_ui(widget, filename):
    loadUi(str(Path(__file__).with_name(filename)), widget)


def adjust_dialog_to_content(dialog, min_text_columns=56):
    if not isinstance(dialog, QDialog):
        return

    font_metrics = dialog.fontMetrics()
    minimum_width = font_metrics.horizontalAdvance("M" * min_text_columns)

    screen = dialog.screen() or QGuiApplication.primaryScreen()
    if screen is not None:
        available_width = screen.availableGeometry().width()
        minimum_width = min(minimum_width, int(available_width * 0.9))

    dialog.setMinimumWidth(minimum_width)
    if dialog.layout() is not None:
        dialog.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    dialog.adjustSize()


def configure_message_box(message_box):
    adjust_dialog_to_content(message_box, min_text_columns=64)
