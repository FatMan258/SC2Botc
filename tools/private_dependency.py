from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from botc_config import MAP_PATH, PROJECT_ROOT, SC2_ROOT
from stormlib_mpq import MPQArchive


PRIVATE_ROOT = PROJECT_ROOT / "private"
TEMPLATE_MOD = PRIVATE_ROOT / "BOTC_Private.template.SC2Mod"
GLOBALS_TEMPLATE = PRIVATE_ROOT / "BOTC_Private_Globals.galaxy.tmpl"
IMPL_TEMPLATE = PRIVATE_ROOT / "BOTC_Private_Impl.galaxy.tmpl"
TRIGGER_TEMPLATE = PRIVATE_ROOT / "BOTC_Private_Triggers.xml.tmpl"
BAN_FILE = PROJECT_ROOT / "data" / "private" / "ban_handles.txt"
GENERATED_DIR = PRIVATE_ROOT / "generated"
MOD_NAME = "BOTC_Private_Core.SC2Mod"
LIBRARY_MEMBERS = (
    r"Base.SC2Data\LibBOTC_Private_h.galaxy",
    r"Base.SC2Data\LibBOTC_Private.galaxy",
)


def _galaxy_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def load_ban_handles() -> list[str]:
    if not BAN_FILE.is_file():
        return []
    handles: list[str] = []
    for raw in BAN_FILE.read_text(encoding="utf-8-sig").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        handles.append(value)
        if len(handles) == 32:
            break
    return handles


def _normalize_galaxy(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def render_globals() -> str:
    return _normalize_galaxy(
        GLOBALS_TEMPLATE.read_text(encoding="utf-8-sig")
    )


def render_impl(handles: list[str]) -> str:
    ban_lines = "\n".join(
        f'    libBOTC_Private_gv_banHandle[{index}] = "{_galaxy_quote(handle)}";'
        for index, handle in enumerate(handles)
    )
    source = IMPL_TEMPLATE.read_text(encoding="utf-8-sig")
    source = source.replace("@@BAN_COUNT@@", str(len(handles)))
    source = source.replace("@@BAN_LINES@@", ban_lines)
    return _normalize_galaxy(source)


def _component_list_with_required_components(components: str) -> str:
    root = ElementTree.fromstring(components)
    existing = {
        ((node.text or "").strip(), node.attrib.get("Type"))
        for node in root.findall("DataComponent")
    }
    for component_type, component_path in (
        ("trig", "Triggers"),
        ("attr", "Attributes"),
    ):
        if (component_path, component_type) in existing:
            continue
        node = ElementTree.SubElement(
            root, "DataComponent", {"Type": component_type}
        )
        node.text = component_path
    ElementTree.indent(root, space="    ")
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        + ElementTree.tostring(root, encoding="unicode").replace(
            "\n", "\r\n"
        )
        + "\r\n"
    )


def build_dependency(install: bool = True) -> Path:
    if not TEMPLATE_MOD.is_file():
        raise FileNotFoundError(f"私有依赖模板不存在：{TEMPLATE_MOD}")
    handles = load_ban_handles()
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output = GENERATED_DIR / MOD_NAME
    shutil.copy2(TEMPLATE_MOD, output)

    with MPQArchive(MAP_PATH, writable=False) as source_map:
        triggers_version = source_map.read_bytes("Triggers.version")
        attributes = source_map.read_bytes("Attributes")
        attributes_version = source_map.read_bytes("Attributes.version")

    with tempfile.TemporaryDirectory(prefix="botc-private-") as temp_dir:
        temp_root = Path(temp_dir)
        header_path = temp_root / "LibBOTC_Private_h.galaxy"
        impl_path = temp_root / "LibBOTC_Private.galaxy"
        triggers_path = temp_root / "Triggers"
        triggers_version_path = temp_root / "Triggers.version"
        attributes_path = temp_root / "Attributes"
        attributes_version_path = temp_root / "Attributes.version"
        components_path = temp_root / "ComponentList.SC2Components"

        header_path.write_bytes(render_globals().encode("utf-8-sig"))
        impl_path.write_bytes(render_impl(handles).encode("utf-8-sig"))
        triggers_path.write_bytes(
            TRIGGER_TEMPLATE.read_text(encoding="utf-8-sig").encode("utf-8")
        )
        triggers_version_path.write_bytes(triggers_version)
        attributes_path.write_bytes(attributes)
        attributes_version_path.write_bytes(attributes_version)

        with MPQArchive(output, writable=False) as archive:
            components = archive.read_text("ComponentList.SC2Components")
        components_path.write_bytes(
            _component_list_with_required_components(components).encode(
                "utf-8"
            )
        )

        payloads = {
            LIBRARY_MEMBERS[0]: header_path,
            LIBRARY_MEMBERS[1]: impl_path,
            "Triggers": triggers_path,
            "Triggers.version": triggers_version_path,
            "Attributes": attributes_path,
            "Attributes.version": attributes_version_path,
            "ComponentList.SC2Components": components_path,
        }
        with MPQArchive(output, writable=True) as archive:
            for member, payload in payloads.items():
                archive.put_file(
                    member, payload, replace=True, compact=False
                )
            archive.compact()

    with MPQArchive(output, writable=False) as archive:
        files = set(archive.listfile())
        missing = [
            member
            for member in (
                *LIBRARY_MEMBERS,
                "Triggers",
                "Triggers.version",
                "Attributes",
                "Attributes.version",
            )
            if member not in files
        ]
        if missing:
            raise ValueError("私有依赖缺少成员：" + ", ".join(missing))
        impl_check = archive.read_text(LIBRARY_MEMBERS[1])
        if f"libBOTC_Private_gv_banHandleN = {len(handles)};" not in impl_check:
            raise ValueError("私有依赖黑名单数量回读不一致")
        triggers_check = archive.read_text("Triggers")
        if "libBOTC_Private_gf_BanCheck();" not in triggers_check:
            raise ValueError("私有依赖触发器没有调用黑名单检查")

    if install:
        mods_dir = SC2_ROOT / "Mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        installed = mods_dir / output.name
        generated_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        installed_hash = (
            hashlib.sha256(installed.read_bytes()).hexdigest()
            if installed.is_file()
            else ""
        )
        if generated_hash != installed_hash:
            shutil.copy2(output, installed)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 BOTC 私有依赖模块")
    parser.add_argument("--no-install", action="store_true")
    args = parser.parse_args(argv)
    output = build_dependency(install=not args.no_install)
    print(f"OK       : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
