from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from botc_config import MAP_PATH, SCRIPT_PATH
from build_map import main as build_main
from galaxy_check import main as check_main
from game_test import main as game_test_main
from role_design import main as role_design_main
from role_workflow import main as role_main
from stormlib_mpq import MPQArchive


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def inspect_map(path: Path) -> int:
    with MPQArchive(path, writable=False) as archive:
        names = archive.listfile()
        keys = {
            name
            for name in names
            if name.lower()
            in {
                "mapscript.galaxy",
                "triggers",
                "componentlist.sc2components",
                "banklist.xml",
            }
        }
        print(f"map     : {path}")
        print(f"members : {len(names)}")
        for key in sorted(keys):
            print(f"member  : {key}")
        if "DocumentInfo" in names:
            document_info = archive.read_text("DocumentInfo")
            dependency_block = re.search(
                r"<Dependencies>(.*?)</Dependencies>",
                document_info,
                re.DOTALL,
            )
            if dependency_block:
                dependencies = re.findall(
                    r"<Value>(.*?)</Value>",
                    dependency_block.group(1),
                    re.DOTALL,
                )
                for dependency in dependencies:
                    print(f"depend  : {dependency.strip()}")
        for name in sorted(
            item for item in names if item.lower().endswith(".galaxy")
        ):
            data = archive.read_bytes(name)
            print(f"galaxy  : {name} ({len(data)} bytes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("用法：botc.py <inspect|check|build|test|role|design> [参数]")
        print("  inspect  检查 SC2Map 包结构")
        print("  check    检查正式 Galaxy 脚本")
        print("  build    直接构建 SC2Map")
        print("  test     部署并启动测试地图")
        print("  role     角色规格工具")
        print("  design   一句话角色 DSL 设计与校验")
        return 0

    command = args.pop(0)
    try:
        if command == "inspect":
            parser = argparse.ArgumentParser(
                prog="botc.py inspect", description="检查 SC2Map 包结构"
            )
            parser.add_argument("map", nargs="?", type=Path, default=MAP_PATH)
            parsed = parser.parse_args(args)
            return inspect_map(parsed.map)
        if command == "check":
            return check_main(args)
        if command == "build":
            return build_main(args)
        if command == "test":
            return game_test_main(args)
        if command == "role":
            return role_main(args)
        if command == "design":
            return role_design_main(args)
    except Exception as error:
        print(f"ERROR    : {error}")
        return 1
    print(f"ERROR    : 未知命令 {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
