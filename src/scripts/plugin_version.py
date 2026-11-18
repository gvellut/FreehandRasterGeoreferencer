import argparse
import os
from pathlib import Path
import re
import subprocess

from qgispluginci.cli import make_parser
from qgispluginci.parameters import Parameters
from qgispluginci.release import release

ROOT = Path(__file__).resolve().parents[2]


class PluginParameters(Parameters):
    def __init__(self, definition):
        super().__init__(definition)
        # QGIS installs the plugin under its package name, including for nested sources.
        self.plugin_zip_directory = Path(self.plugin_path).name

    @staticmethod
    def archive_name(plugin_name: str, release_version: str) -> str:
        # Keep the archive at the repository root when the source is under src/.
        return Parameters.archive_name(Path(plugin_name).name, release_version)


def sync_metadata(version: str) -> None:
    path = ROOT / "src" / "fhrgr" / "metadata.txt"
    with path.open(encoding="utf-8", newline="") as metadata_file:
        metadata = metadata_file.read()
    updated, count = re.subn(r"(?m)^version=[^\r\n]*", f"version={version}", metadata)
    if count != 1:
        raise SystemExit("Expected exactly one version field in src/fhrgr/metadata.txt")
    if updated != metadata:
        path.write_text(updated, encoding="utf-8", newline="")
    print(f"src/fhrgr/metadata.txt version is {version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Use the version from pyproject.toml")
    parser.add_argument("action", choices=("sync", "package", "release"))
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

    os.chdir(ROOT)
    ci_args = make_parser().parse_args([args.action, version, *args.package_options])
    Parameters.validate_args(ci_args)
    parameters = PluginParameters.make_from(args=ci_args)
    release_options = {}
    if args.action == "release":
        release_options = {
            "release_tag": ci_args.release_tag,
            "github_token": ci_args.github_token,
            "upload_plugin_repo_github": ci_args.create_plugin_repo,
            "alternative_repo_url": ci_args.alternative_repo_url,
            "qgis_token": ci_args.qgis_token,
            "osgeo_username": ci_args.osgeo_username,
            "osgeo_password": ci_args.osgeo_password,
        }
    release(
        parameters,
        release_version=version,
        tx_api_token=ci_args.transifex_token,
        allow_uncommitted_changes=ci_args.allow_uncommitted_changes,
        plugin_repo_url=getattr(ci_args, "plugin_repo_url", None),
        plugin_repo_stylesheet=not ci_args.no_repository_stylesheet,
        disable_submodule_update=ci_args.disable_submodule_update,
        asset_paths=ci_args.asset_path,
        **release_options,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
