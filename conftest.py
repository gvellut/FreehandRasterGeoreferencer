def pytest_addoption(parser):
    parser.addoption(
        "--qgis-app",
        default="/Applications/QGIS4.app",
        metavar="APP_BUNDLE",
        help="Path to the QGIS 4 app bundle for Desktop tests (default: %(default)s).",
    )
