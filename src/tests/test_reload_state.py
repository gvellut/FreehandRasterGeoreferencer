"""Optional PyQGIS checks for the handoff used by Plugin Reloader."""

import importlib
from types import SimpleNamespace

import pytest

pytest.importorskip("qgis.core")
pytest.importorskip("osgeo.gdal")

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsMapSettings,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication, QObject, pyqtSignal  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402

from fhrgr import layer as layer_module, reload_state  # noqa: E402


class Canvas(QObject):
    destinationCrsChanged = pyqtSignal()

    def mapSettings(self):
        settings = QgsMapSettings()
        settings.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        return settings


class Interface:
    def __init__(self):
        self.canvas = Canvas()
        self.active_layer = None
        self.messages = []

    def mapCanvas(self):
        return self.canvas

    def activeLayer(self):
        return self.active_layer

    def setActiveLayer(self, layer):
        self.active_layer = layer
        return True

    def messageBar(self):
        return SimpleNamespace(pushMessage=lambda *args: self.messages.append(args))


@pytest.fixture
def plugin(qgis_application):
    project = QgsProject.instance()
    project.clear()
    reload_state._clear_pending_state(project)
    plugin = SimpleNamespace(iface=Interface(), layers={})
    registry = QgsApplication.pluginLayerRegistry()
    registry.addPluginLayerType(
        layer_module.FreehandRasterGeoreferencerLayerType(plugin)
    )
    yield plugin
    registry.removePluginLayerType(
        layer_module.FreehandRasterGeoreferencerLayer.LAYER_TYPE
    )
    project.clear()
    reload_state._clear_pending_state(project)
    QCoreApplication.processEvents()


def add_raster(plugin, tmp_path, name):
    path = tmp_path / f"{name}.png"
    image = QImage(4, 3, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    assert image.save(str(path), "PNG")
    layer = layer_module.FreehandRasterGeoreferencerLayer(plugin, str(path), name, None)
    assert layer.initialized
    QgsProject.instance().addMapLayer(layer, False)
    return layer


def tree_description(group):
    result = []
    for node in group.children():
        if isinstance(node, reload_state.QgsLayerTreeGroup):
            result.append((node.name(), tree_description(node)))
        else:
            result.append((
                node.layerId(),
                node.itemVisibilityChecked(),
                node.isExpanded(),
                node.customProperty("test/color"),
            ))
    return result


def test_reload_recreates_layers_and_preserves_project_state(plugin, tmp_path):
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    # Identically named groups must retain their distinct layer placements.
    root.addGroup("Maps")
    group = root.addGroup("Maps").addGroup("Nested")
    reference = QgsVectorLayer("Point?crs=EPSG:3857", "Reference", "memory")
    assert reference.isValid()
    project.addMapLayer(reference, False)
    group.addLayer(reference)
    first = add_raster(plugin, tmp_path, "first")
    first.setName("Renamed raster")
    first.set_center(QgsPointXY(123, 456))
    first.set_rotation(12.345)
    first.set_scale(2, 3)
    first.set_transparency(67)
    first.set_blend_mode_by_name("Multiply")
    first.commit_transform_parameters()
    first.history = [{"action": "move", "center": QgsPointXY(10, 20)}]
    first.setCustomProperty("test/extra", "preserved")
    first_node = group.insertLayer(0, first)
    first_node.setItemVisibilityChecked(False)
    first_node.setExpanded(False)
    first_node.setCustomProperty("test/color", "red")
    second = add_raster(plugin, tmp_path, "second")
    group.addLayer(second)
    root.addLayer(first)
    order = [second.id(), reference.id(), first.id()]
    root.setCustomLayerOrder([second, reference, first])
    root.setHasCustomLayerOrder(True)
    plugin.iface.setActiveLayer(first)
    first_id, second_id = first.id(), second.id()
    original_class = type(first)
    expected_tree = tree_description(root)
    project.setDirty(False)

    # Include project-loaded layers even when the plugin bookkeeping is empty.
    assert plugin.layers == {}
    state = reload_state.capture_reload_state(plugin.iface)
    QgsApplication.pluginLayerRegistry().removePluginLayerType(
        original_class.LAYER_TYPE
    )
    reload_state.store_reload_state(state)
    assert project.mapLayer(first_id) is None
    assert project.mapLayer(second_id) is None

    # A real reload creates fresh Python classes; no old layer instances survive.
    importlib.reload(layer_module)
    importlib.reload(reload_state)
    replacement = SimpleNamespace(iface=Interface(), layers={})
    registry = QgsApplication.pluginLayerRegistry()
    registry.addPluginLayerType(
        layer_module.FreehandRasterGeoreferencerLayerType(replacement)
    )
    pending = reload_state.take_reload_state()
    QCoreApplication.processEvents()
    assert reload_state._pending_state(project) is not None
    reload_state.restore_reload_state(replacement, pending)

    restored = project.mapLayer(first_id)
    assert type(restored) is layer_module.FreehandRasterGeoreferencerLayer
    assert type(restored) is not original_class
    assert restored.plugin is replacement
    assert restored.name() == "Renamed raster"
    assert restored.center == QgsPointXY(123, 456)
    assert restored.rotation == 12.345
    assert (restored.x_scale, restored.y_scale) == (2, 3)
    assert restored.transparency == 67
    assert restored.blend_mode_name == "Multiply"
    assert restored.customProperty("test/extra") == "preserved"
    assert restored.history == [{"action": "move", "center": QgsPointXY(10, 20)}]
    assert restored.initialized
    assert (restored.image.width(), restored.image.height()) == (4, 3)
    assert tree_description(root) == expected_tree
    assert [layer.id() for layer in root.customLayerOrder()] == order
    assert root.hasCustomLayerOrder()
    assert replacement.iface.activeLayer() is restored
    assert set(replacement.layers) == {first_id, second_id}
    assert project.mapLayer(reference.id()) is reference
    assert not project.isDirty()
    assert reload_state._pending_state(project) is None
    assert not any(
        message[2] == Qgis.MessageLevel.Critical
        for message in replacement.iface.messages
    )


def test_ordinary_unload_snapshot_expires(plugin, tmp_path):
    layer = add_raster(plugin, tmp_path, "raster")
    QgsProject.instance().layerTreeRoot().addLayer(layer)
    reload_state.store_reload_state(reload_state.capture_reload_state(plugin.iface))
    QCoreApplication.processEvents()
    assert reload_state.take_reload_state() is None


def test_repeated_handoffs_do_not_expire_the_new_snapshot(plugin, tmp_path):
    layer = add_raster(plugin, tmp_path, "raster")
    QgsProject.instance().layerTreeRoot().addLayer(layer)
    for _ in range(2):
        state = reload_state.capture_reload_state(plugin.iface)
        reload_state.store_reload_state(state)
        assert reload_state.take_reload_state() is not None
    QCoreApplication.processEvents()
    assert reload_state._pending_state(QgsProject.instance()) == state


def test_snapshot_is_not_restored_into_another_project(plugin, tmp_path):
    layer = add_raster(plugin, tmp_path, "raster")
    QgsProject.instance().layerTreeRoot().addLayer(layer)
    reload_state.store_reload_state(reload_state.capture_reload_state(plugin.iface))
    QgsProject.instance().setFileName(str(tmp_path / "another.qgz"))
    assert reload_state.take_reload_state() is None


def test_claimed_snapshot_is_discarded_when_an_unsaved_project_is_cleared(
    plugin, tmp_path
):
    layer = add_raster(plugin, tmp_path, "raster")
    QgsProject.instance().layerTreeRoot().addLayer(layer)
    reload_state.store_reload_state(reload_state.capture_reload_state(plugin.iface))
    assert reload_state.take_reload_state() is not None
    QgsProject.instance().clear()
    assert reload_state.take_reload_state() is None
