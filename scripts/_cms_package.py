"""
Shared helper for locating the CMS HHS-HCC DIY software package on disk. Used by both
build_v08_reference_data.py and cross_validate_cms.py.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def find_cms_root() -> Path:
    env_path = os.environ.get("CMS_PACKAGE_DIR")
    if env_path:
        return Path(env_path)
    candidates = sorted(REPO_ROOT.parent.glob("HHS_HCC_software_package*"))
    if not candidates:
        raise SystemExit(
            "Could not locate the CMS HHS_HCC software package directory. "
            "Set the CMS_PACKAGE_DIR environment variable to its path, or place it "
            "as a sibling directory of this repo (e.g. ../HHS_HCC_software_package_*)."
        )
    return candidates[-1]
