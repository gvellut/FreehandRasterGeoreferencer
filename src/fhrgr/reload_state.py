"""Hand layer state to the next plugin instance during a synchronous reload."""

from qgis.core import (
    Qgis,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
    QgsReadWriteContext,
)
from qgis.PyQt.QtCore import QObject, QTimer, pyqtSlot
from qgis.PyQt.QtXml import QDomDocument

from .layer import FreehandRasterGeoreferencerLayer

HANDOFF_OBJECT_NAME = "_fhrgr_pending_reload"


class _ReloadHandoff(QObject):
    def __init__(self, project, state):
        super().__init__(project)
        self.setObjectName(HANDOFF_OBJECT_NAME)
        self.setProperty("state", state)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.expire)
        project.aboutToBeCleared.connect(self.expire)
        self.timer.start(0)

    @pyqtSlot()
    def expire(self):
        self.setProperty("state", None)
        self.setObjectName("")
        self.deleteLater()


def _pending_state(project):
    handoff = project.findChild(QObject, HANDOFF_OBJECT_NAME)
    return handoff.property("state") if handoff is not None else None


def _clear_pending_state(project):
    handoff = project.findChild(QObject, HANDOFF_OBJECT_NAME)
    if handoff is not None:
        handoff.setProperty("state", None)
        handoff.setObjectName("")
        handoff.deleteLater()


def _context(project):
    context = QgsReadWriteContext()
    context.setPathResolver(project.pathResolver())
    context.setTransformContext(project.transformContext())
    return context


def _tree_nodes(group, layer_ids, context, group_path=()):
    nodes = []
    group_index = 0
    for index, node in enumerate(group.children()):
        if isinstance(node, QgsLayerTreeGroup):
            # Count only groups: removing layers must not change this path.
            nodes.extend(
                _tree_nodes(node, layer_ids, context, (*group_path, group_index))
            )
            group_index += 1
        elif isinstance(node, QgsLayerTreeLayer) and node.layerId() in layer_ids:
            document = QDomDocument()
            parent = document.createElement("reload")
            document.appendChild(parent)
            node.writeXml(parent, context)
            nodes.append({
                "layer_id": node.layerId(),
                "group_path": list(group_path),
                "index": index,
                "xml": document.toString(),
            })
    return nodes


def capture_reload_state(iface):
    project = QgsProject.instance()
    context = _context(project)
    layers = []
    for layer in project.mapLayers().values():
        if (
            layer.type() != Qgis.LayerType.Plugin
            or layer.pluginLayerType() != FreehandRasterGeoreferencerLayer.LAYER_TYPE
        ):
            continue

        document = QDomDocument()
        element = document.createElement("maplayer")
        document.appendChild(element)
        if not layer.writeLayerXml(element, document, context):
            raise RuntimeError(f"Could not preserve raster layer {layer.name()!r}")
        history = []
        for entry in layer.history:
            saved_entry = entry.copy()
            if "center" in saved_entry:
                center = saved_entry["center"]
                saved_entry["center"] = [center.x(), center.y()]
            history.append(saved_entry)
        layers.append({
            "id": layer.id(),
            "xml": document.toString(),
            "history": history,
            "initialized": layer.initialized,
            "error": layer.error,
            "load_error": layer.load_error,
            "valid": layer.isValid(),
        })

    root = project.layerTreeRoot()
    layer_ids = {layer["id"] for layer in layers}
    nodes = _tree_nodes(root, layer_ids, context)
    pending = _pending_state(project)
    if pending and pending["project_file"] == project.fileName():
        # Retain any layers that failed to restore on the previous attempt.
        missing = [layer for layer in pending["layers"] if layer["id"] not in layer_ids]
        node_ids = {node["layer_id"] for node in nodes}
        layers.extend(missing)
        nodes.extend(
            node for node in pending["nodes"] if node["layer_id"] not in node_ids
        )
    if not layers:
        return None

    active_layer = iface.activeLayer()
    return {
        "project_file": project.fileName(),
        "dirty": project.isDirty(),
        "active_layer_id": active_layer.id() if active_layer is not None else None,
        "custom_order": root.hasCustomLayerOrder(),
        "layer_order": [layer.id() for layer in root.customLayerOrder()],
        "layers": layers,
        "nodes": nodes,
    }


def store_reload_state(state):
    if state is None:
        return
    project = QgsProject.instance()
    _clear_pending_state(project)
    # Plugin Reloader starts the new instance before returning to the event loop.
    # An ordinary unload must not leave a snapshot for a later plugin activation.
    _ReloadHandoff(project, state)


def take_reload_state():
    project = QgsProject.instance()
    handoff = project.findChild(QObject, HANDOFF_OBJECT_NAME)
    if handoff is None:
        return None
    state = handoff.property("state")
    if state["project_file"] != project.fileName():
        _clear_pending_state(project)
        return None
    # Claim the snapshot before GUI construction can process any pending timers.
    handoff.findChild(QTimer).stop()
    return state


def _read_document(xml):
    document = QDomDocument()
    valid, message, _, _ = document.setContent(xml)
    if not valid:
        raise ValueError(message)
    return document


def restore_reload_state(plugin, state):
    if state is None:
        return
    project = QgsProject.instance()
    context = _context(project)
    try:
        for saved_layer in state["layers"]:
            layer = FreehandRasterGeoreferencerLayer(plugin, None, "", None)
            try:
                document = _read_document(saved_layer["xml"])
                if not layer.readLayerXml(document.documentElement(), context):
                    raise RuntimeError("Could not read the preserved raster layer")
                if layer.id() != saved_layer["id"] and not layer.setId(
                    saved_layer["id"]
                ):
                    raise RuntimeError("Could not restore the raster layer ID")
                if saved_layer["initialized"]:
                    # Load the image before enabling tools for the restored layer.
                    saved_crs = layer.crs()
                    layer.initialize_layer()
                    layer.setCrs(saved_crs)
                else:
                    layer.error = saved_layer["error"]
                    layer.load_error = saved_layer["load_error"]
                    layer.setValid(saved_layer["valid"])
                layer.history = []
                for entry in saved_layer["history"]:
                    restored_entry = entry.copy()
                    if "center" in restored_entry:
                        restored_entry["center"] = QgsPointXY(*restored_entry["center"])
                    layer.history.append(restored_entry)
                if project.addMapLayer(layer, False) is None:
                    raise RuntimeError("Could not add the restored raster layer")
            except (RuntimeError, TypeError, ValueError):
                layer.deleteLater()
                raise
            plugin.layers[layer.id()] = layer

        root = project.layerTreeRoot()
        nodes_to_insert = []
        for saved_node in sorted(
            state["nodes"], key=lambda node: (node["group_path"], node["index"])
        ):
            group = root
            for index in saved_node["group_path"]:
                groups = [
                    node
                    for node in group.children()
                    if isinstance(node, QgsLayerTreeGroup)
                ]
                group = groups[index]
            document = _read_document(saved_node["xml"])
            node = QgsLayerTreeLayer.readXml(
                document.documentElement().firstChildElement(), project
            )
            if node is None:
                raise RuntimeError("Could not restore the raster layer tree entry")
            nodes_to_insert.append((
                group,
                saved_node["index"],
                node,
                node.itemVisibilityChecked(),
            ))
        for group, index, node, _ in nodes_to_insert:
            group.insertChildNode(index, node)
        # Group visibility rules may have changed checks while inserting nodes.
        for _, _, node, checked in nodes_to_insert:
            node.setItemVisibilityChecked(checked)

        root.setCustomLayerOrder([
            layer
            for layer_id in state["layer_order"]
            if (layer := project.mapLayer(layer_id)) is not None
        ])
        root.setHasCustomLayerOrder(state["custom_order"])
        plugin.iface.setActiveLayer(project.mapLayer(state["active_layer_id"]))
        project.setDirty(state["dirty"])
        _clear_pending_state(project)
    except (IndexError, RuntimeError, TypeError, ValueError) as ex:
        # Keep the claimed snapshot available for recovery on the next reload.
        QgsMessageLog.logMessage(
            f"Could not restore raster layers after reload: {ex}",
            "Freehand raster georeferencer",
            Qgis.MessageLevel.Critical,
        )
        plugin.iface.messageBar().pushMessage(
            "Freehand raster georeferencer",
            "Some raster layers could not be restored after reload. "
            "See the QGIS Message log for details.",
            Qgis.MessageLevel.Critical,
        )
