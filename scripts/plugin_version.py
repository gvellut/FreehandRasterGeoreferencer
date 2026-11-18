import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sync_metadata(version: str) -> None:
    path = ROOT / "fhrgr" / "metadata.txt"
    with path.open(encoding="utf-8", newline="") as metadata_file:
        metadata = metadata_file.read()
    updated, count = re.subn(r"(?m)^version=[^\r\n]*", f"version={version}", metadata)
    if count != 1:
        raise SystemExit("Expected exactly one version field in fhrgr/metadata.txt")
    if updated != metadata:
        path.write_text(updated, encoding="utf-8", newline="")
    print(f"fhrgr/metadata.txt version is {version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Use the version from pyproject.toml")
    parser.add_argument("action", choices=("sync", "package"))
    parser.add_argument("package_options", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "sync" and args.package_options:
        parser.error("sync takes no arguments")

    version = subprocess.check_output(
        ["uv", "version", "--short"], cwd=ROOT, text=True
    ).strip()
    if args.action == "sync":
        sync_metadata(version)
        return 0

    return subprocess.run(
        ["qgis-plugin-ci", "package", version, *args.package_options],
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
