"""Run the requested tests from the QGIS Desktop --code hook."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import traceback

from qgis.PyQt.QtCore import QCoreApplication, QTimer


def run_tests():
    root = Path.cwd()
    report = Path(os.environ["FHRGR_QGIS_TEST_REPORT"])
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        try:
            sys.path.insert(0, os.environ["FHRGR_QGIS_TEST_DEPS"])
            import pytest

            status = int(
                pytest.main([
                    "-c",
                    str(root / "pyproject.toml"),
                    "-p",
                    "no:cacheprovider",
                    "--basetemp",
                    str(report.with_name("pytest-tmp")),
                    "--capture=sys",
                    "--color=no",
                    "-v",
                    "-ra",
                    os.environ["FHRGR_QGIS_TEST_PATH"],
                ])
            )
        except Exception:
            traceback.print_exc()
            status = 1
    report.write_text(
        json.dumps({"status": status, "output": output.getvalue()}), encoding="utf-8"
    )
    QCoreApplication.exit(status)


QTimer.singleShot(0, run_tests)
