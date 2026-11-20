import pytest
from qgis.core import Qgis, QgsApplication
import qgis.utils


@pytest.fixture(scope="session", autouse=True)
def qgis_application():
    application = QgsApplication.instance()
    if application is None or qgis.utils.iface is None:
        pytest.fail("Run the QGIS tests through src/tests/test_qgis_desktop.py.")
    if not 40000 <= Qgis.QGIS_VERSION_INT < 50000:
        pytest.fail(f"The QGIS tests require QGIS 4. Found {Qgis.QGIS_VERSION}.")
    return application
