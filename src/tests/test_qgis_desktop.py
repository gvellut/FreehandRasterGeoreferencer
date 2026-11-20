import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
QGIS_TESTS = ROOT / "src" / "qgis_tests"
DEPENDENCIES = ROOT / ".qgis-test-deps" / "site-packages"
QGIS_TIMEOUT_SECONDS = 60

pytestmark = [
    pytest.mark.qgis_desktop,
    pytest.mark.skipif(
        sys.platform != "darwin", reason="Requires a macOS QGIS 4 app bundle"
    ),
]


def qgis_bundle_paths(app_bundle):
    bundle = Path(app_bundle).expanduser()
    contents = bundle.resolve() / "Contents"
    try:
        with (contents / "Info.plist").open("rb") as metadata:
            executable = (
                contents / "MacOS" / plistlib.load(metadata)["CFBundleExecutable"]
            )
    except (OSError, KeyError, ValueError, plistlib.InvalidFileException) as error:
        pytest.fail(
            f"Pass a QGIS 4 app bundle path with --qgis-app. {error}", pytrace=False
        )

    if not executable.is_file() or not os.access(executable, os.X_OK):
        pytest.fail(
            f"QGIS executable is missing or cannot be run: {executable}", pytrace=False
        )
    return executable, contents / "PlugIns"


def _run_qgis_tests(tmp_path, request, *, scale_factor, test_path):
    executable, qt_plugins = qgis_bundle_paths(request.config.getoption("--qgis-app"))
    if not (DEPENDENCIES / "pytest" / "__init__.py").is_file():
        pytest.fail(
            "Run uv run task setup-qgis-tests to stage pytest for QGIS.", pytrace=False
        )

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    settings = tmp_path / "qgis-settings.ini"
    # Keep startup off the Keychain and prevent font downloads during shutdown.
    settings.write_text(
        "[authentication]\nuse-password-helper=false\n\n"
        "[fonts]\ndownloadMissingFonts=false\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "result.json"
    log_path = tmp_path / "qgis.log"
    env = os.environ.copy()
    # Give the embedded Python and QGIS their own import, pytest, and profile settings.
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "QGIS_CUSTOM_CONFIG_PATH",
    ):
        env.pop(key, None)
    env.update(
        QT_PLUGIN_PATH=str(qt_plugins),
        QT_QPA_PLATFORM="offscreen",
        QT_SCALE_FACTOR=scale_factor,
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        FHRGR_QGIS_TEST_DEPS=str(DEPENDENCIES),
        FHRGR_QGIS_TEST_PATH=str(test_path),
        FHRGR_QGIS_TEST_REPORT=str(report_path),
    )
    command = [
        executable,
        "--nologo",
        "--noversioncheck",
        "--noplugins",
        "--profiles-path",
        profiles,
        "--profile",
        "pytest",
        "--globalsettingsfile",
        settings,
        "--code",
        QGIS_TESTS / "run_tests.py",
    ]

    try:
        with log_path.open("w") as log:
            process = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=QGIS_TIMEOUT_SECONDS,
                check=False,
            )
    except subprocess.TimeoutExpired:
        request.node.add_report_section(
            "call", "QGIS process", log_path.read_text(errors="replace")
        )
        pytest.fail(
            f"QGIS did not finish within {QGIS_TIMEOUT_SECONDS} seconds.", pytrace=False
        )
    except OSError as error:
        pytest.fail(f"Could not launch QGIS: {error}", pytrace=False)

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        output, status = report["output"], report["status"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        request.node.add_report_section(
            "call", "QGIS process", log_path.read_text(errors="replace")
        )
        pytest.fail(
            f"QGIS exited with status {process.returncode} without a readable "
            f"pytest report. {error}",
            pytrace=False,
        )

    request.node.add_report_section("call", "QGIS pytest", output)
    if status or process.returncode:
        request.node.add_report_section(
            "call", "QGIS process", log_path.read_text(errors="replace")
        )
        pytest.fail(
            f"Inner pytest exited with status {status}. "
            f"QGIS exited with status {process.returncode}.",
            pytrace=False,
        )


def test_qgis_desktop(tmp_path, request):
    _run_qgis_tests(tmp_path, request, scale_factor="1", test_path=QGIS_TESTS)


@pytest.mark.parametrize("scale_factor", ["1.5", "2"], ids=["1.5x", "2x"])
def test_qgis_dialog_hidpi(tmp_path, request, scale_factor):
    _run_qgis_tests(
        tmp_path,
        request,
        scale_factor=scale_factor,
        test_path=QGIS_TESTS / "test_dialog_layout.py",
    )
