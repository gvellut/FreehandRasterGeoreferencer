from pathlib import Path


def icon_path(filename):
    return str(Path(__file__).with_name("icons") / filename)
