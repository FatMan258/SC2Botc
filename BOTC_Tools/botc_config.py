from __future__ import annotations

import os
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TOOL_ROOT.parent

SCRIPT_PATH = Path(
    os.environ.get("BOTC_SCRIPT", str(PROJECT_ROOT / "BOTC_脚本_粘贴用.txt"))
)
MAP_PATH = Path(
    os.environ.get("BOTC_MAP", str(PROJECT_ROOT / "base_map.SC2Map"))
)
UI_MOD_PATH = Path(
    os.environ.get("BOTC_UI_MOD", str(PROJECT_ROOT / "UIHIDE55.SC2Mod"))
)
BUILD_DIR = Path(
    os.environ.get("BOTC_BUILD_DIR", str(PROJECT_ROOT / "build"))
)
ROLE_SPEC_DIR = TOOL_ROOT / "role_specs"
STORM_DLL = TOOL_ROOT / "vendor" / "StormLib.dll"

SC2_ROOT = Path(
    os.environ.get(
        "BOTC_SC2_ROOT", r"C:\Program Files (x86)\StarCraft II"
    )
)
SC2_SWITCHER = SC2_ROOT / "Support64" / "SC2Switcher_x64.exe"
SC2_TEST_DIR = PROJECT_ROOT / "Test"
GAME_LOG_DIR = (
    Path.home() / "Documents" / "StarCraft II" / "GameLogs"
)


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在：{path}")
    return path


def ensure_build_dir(path: Path | None = None) -> Path:
    target = path or BUILD_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target
