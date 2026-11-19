import os

import pytest


@pytest.fixture(scope="session")
def qgis_application():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qgis_core = pytest.importorskip("qgis.core")
    application = qgis_core.QgsApplication.instance()
    owned = application is None
    if owned:
        application = qgis_core.QgsApplication([], False)
        application.initQgis()
    yield application
    if owned:
        application.exitQgis()
