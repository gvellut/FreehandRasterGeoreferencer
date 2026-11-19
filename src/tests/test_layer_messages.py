"""Optional PyQGIS checks for delivery of raster layer messages."""

from threading import Thread
from types import SimpleNamespace

import pytest

pytest.importorskip("qgis.core")
pytest.importorskip("osgeo.gdal")

from qgis.core import Qgis  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication, QEvent, QThread  # noqa: E402

from fhrgr import layer as layer_module  # noqa: E402


@pytest.mark.parametrize("destroy_before_delivery", [False, True])
def test_layer_message_bar_delivers_on_main_thread(
    qgis_application, destroy_before_delivery
):
    main_thread = qgis_application.thread()
    delivered = []

    def push_message(*args):
        delivered.append((QThread.currentThread() == main_thread, args))

    message_bar = SimpleNamespace(pushMessage=push_message)
    iface = SimpleNamespace(messageBar=lambda: message_bar)
    plugin = SimpleNamespace(iface=iface)
    layer = layer_module.FreehandRasterGeoreferencerLayer(plugin, None, "", None)

    info = (
        "Georeferencing loaded",
        "Found existing georeferencing",
        Qgis.MessageLevel.Info,
        3,
    )
    warning = (
        "Raster display",
        "Applied raster alpha band for display.",
        Qgis.MessageLevel.Warning,
        10,
    )
    expected = [(True, info)]
    layer.show_bar_message(*info)
    assert delivered == expected

    worker = Thread(target=layer.show_bar_message, args=warning, daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert delivered == expected

    if not destroy_before_delivery:
        QCoreApplication.processEvents()
        expected.append((True, warning))
    layer.deleteLater()
    # Process deletion before the pending slot call in the destruction case.
    QCoreApplication.sendPostedEvents(layer, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    assert delivered == expected
