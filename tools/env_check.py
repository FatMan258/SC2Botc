from __future__ import annotations

from pathlib import Path

from botc_config import (
    MAP_PATH,
    SC2_SWITCHER,
    SCRIPT_PATH,
    STORM_DLL,
)


LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def is_lfs_pointer(path: Path) -> bool:
    try:
        with Path(path).open("rb") as handle:
            return handle.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX
    except OSError:
        return False


def check_file(label: str, path: Path, required: bool) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        if required:
            errors.append(f"缺少{label}：{path}")
        else:
            print(f"WARN     : 未找到可选的{label}：{path}")
        return errors
    if is_lfs_pointer(path):
        if required:
            errors.append(
                f"{label}仍是指向 Git LFS 的文本指针，请执行 git lfs pull：{path}"
            )
        else:
            print(f"WARN     : 可选的{label}仍是 Git LFS 指针：{path}")
        return errors
    print(f"OK       : {label}：{path}")
    return errors


def doctor() -> int:
    errors: list[str] = []
    errors.extend(check_file("Galaxy 脚本", SCRIPT_PATH, True))
    errors.extend(check_file("基础地图", MAP_PATH, True))
    errors.extend(check_file("StormLib", STORM_DLL, True))
    errors.extend(check_file("SC2 启动器", SC2_SWITCHER, False))
    if errors:
        print("\n环境尚未就绪：")
        for error in errors:
            print(f"- {error}")
        print("\n请确认已执行 git lfs install 和 git lfs pull。")
        return 1
    print("\n环境检查通过：可以直接运行 tools\\botc.cmd build。")
    return 0


def main(argv: list[str] | None = None) -> int:
    del argv
    return doctor()


if __name__ == "__main__":
    raise SystemExit(main())
