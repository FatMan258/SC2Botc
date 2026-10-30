from __future__ import annotations

import argparse
import csv
import io
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from botc_config import (
    GAME_LOG_DIR,
    SC2_ROOT,
    SC2_SWITCHER,
    SC2_TEST_DIR,
    require_file,
)
from stormlib_mpq import MPQArchive


MIN_OBSERVE_SECONDS = 65


def find_game_exe() -> Path:
    versions = SC2_ROOT / "Versions"
    candidates: list[tuple[int, Path]] = []
    for directory in versions.glob("Base*"):
        executable = directory / "SC2_x64.exe"
        if not executable.is_file():
            continue
        suffix = directory.name.removeprefix("Base")
        if suffix.isdigit():
            candidates.append((int(suffix), executable))
    if not candidates:
        raise FileNotFoundError(f"未找到 SC2_x64.exe：{versions}")
    return max(candidates)[1]


def running_game_pids() -> set[int]:
    result = subprocess.run(
        [
            "tasklist.exe",
            "/FI",
            "IMAGENAME eq SC2_x64.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[int] = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[0].lower() == "sc2_x64.exe":
            try:
                pids.add(int(row[1]))
            except ValueError:
                pass
    return pids


def terminate_game(pids: set[int]) -> None:
    for pid in sorted(pids):
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/F"],
            capture_output=True,
            check=False,
        )


def newest_script_error(since: float) -> Path | None:
    if not GAME_LOG_DIR.is_dir():
        return None
    files = [
        path
        for path in GAME_LOG_DIR.glob("*ScriptError.txt")
        if path.stat().st_mtime >= since
    ]
    return max(files, key=lambda path: path.stat().st_mtime, default=None)


def new_log_files(since: float, suffix: str) -> list[Path]:
    if not GAME_LOG_DIR.is_dir():
        return []
    return sorted(
        (
            path
            for path in GAME_LOG_DIR.glob(f"*{suffix}")
            if path.stat().st_mtime >= since
        ),
        key=lambda path: path.stat().st_mtime,
    )


def detect_melee_mod(map_path: Path) -> str | None:
    with MPQArchive(map_path, writable=False) as archive:
        document_info = archive.read_bytes("DocumentInfo").decode(
            "utf-8-sig", "replace"
        )
    match = re.search(
        r"file:Campaigns/([^/<>]+)\.SC2Campaign", document_info, re.IGNORECASE
    )
    return match.group(1) if match else None


def deploy_map(source: Path, name: str | None = None) -> Path:
    source = require_file(Path(source), "测试地图")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_name = name or f"botc-test-{stamp}"
    target = SC2_TEST_DIR / f"{target_name}.SC2Map"
    SC2_TEST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def launch_test(
    map_path: Path,
    name: str | None,
    wait: int,
    keep_map: bool,
    keep_game: bool,
    forced_melee_mod: str | None,
) -> int:
    require_file(SC2_SWITCHER, "SC2Switcher")
    game_exe = find_game_exe()
    existing_pids = running_game_pids()
    if existing_pids:
        raise RuntimeError(
            "检测到 SC2_x64.exe 已在运行。请先自行退出游戏，再运行测试工具。"
        )

    deployed = deploy_map(map_path, name)
    melee_mod = forced_melee_mod or detect_melee_mod(map_path)
    started_at = time.time()
    env = os.environ.copy()
    env["PATH"] = str(SC2_ROOT / "Support64") + ";" + env.get("PATH", "")
    args = [
        str(SC2_SWITCHER),
        "-run",
        str(deployed),
        "-displaymode",
        "2",
        "-preload",
        "1",
        "-NoUserCheats",
        "-reloadcheck",
        "-difficulty",
        "2",
        "-speed",
        "2",
    ]
    if melee_mod:
        args.extend(["-meleeMod", melee_mod])
    process = subprocess.Popen(args, cwd=str(game_exe.parent), env=env)
    print(f"deployed : {deployed}")
    print(f"launcher : {SC2_SWITCHER}")
    print(f"game     : {game_exe}")
    print(f"melee    : {melee_mod or '(none)'}")
    print(f"pid      : {process.pid}")

    deadline = time.time() + max(wait, 15)
    saw_game = False
    saw_error = False
    launched_pids: set[int] = set()
    result = 1
    while time.time() < deadline:
        time.sleep(2)
        error = newest_script_error(started_at)
        if error is not None:
            print(f"FAIL     : {error}")
            print(error.read_text(encoding="utf-8", errors="replace")[:4000])
            saw_error = True
            result = 1
            break
        current_pids = running_game_pids()
        if current_pids:
            saw_game = True
            launched_pids.update(current_pids - existing_pids)
            if time.time() - started_at >= MIN_OBSERVE_SECONDS:
                if new_log_files(started_at, "UI.txt"):
                    print("UI_WARN  : 本次启动产生了新的 UI.txt，请检查界面布局错误")
                print("ALIVE    : 游戏进程仍在运行，未发现新的 ScriptError")
                print(
                    "VERIFY   : 若画面停在网易账号登录/“无法运行游戏”，"
                    "请先登录 Battle.net；游戏自带线上依赖可能尚未加载"
                )
                result = 0
                break

    if result == 1 and saw_game and not saw_error:
        print("UNKNOWN  : 游戏仍在运行，但等待时间内无法确认地图是否完成加载")
        result = 2
    elif result == 1 and not saw_error:
        print("FAIL     : 未检测到 SC2_x64.exe")

    if not keep_game:
        terminate_game(launched_pids)
    if not keep_map:
        deployed.unlink(missing_ok=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="部署并启动 BOTC 测试地图")
    parser.add_argument("map", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--wait", type=int, default=90)
    parser.add_argument(
        "--melee-mod",
        help="覆盖自动检测到的战役依赖，例如 Void",
    )
    parser.add_argument("--keep-map", action="store_true")
    parser.add_argument("--keep-game", action="store_true")
    args = parser.parse_args(argv)

    try:
        return launch_test(
            args.map,
            args.name,
            args.wait,
            args.keep_map,
            args.keep_game,
            args.melee_mod,
        )
    except Exception as error:
        print(f"FAIL     : {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
