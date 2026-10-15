"""Build the Windows app, branded Setup.exe, and a clean source/license bundle."""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import zipfile
from importlib.metadata import distribution
from pathlib import Path

from PyQt6.QtCore import Qt
from packaging.requirements import Requirement
from PyQt6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build" / "release"
APP_DIST = BUILD_ROOT / "app"
SETUP_DIST = BUILD_ROOT / "setup"
RELEASE_DIR = ROOT / "release"
RUNTIME_PACKAGES = (
    "PyQt6",
    "PyMuPDF",
    "cryptography",
    "python-dotenv",
    "keyring",
    "requests",
)


def _run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _write_icon() -> Path:
    source = ROOT / "icon.png"
    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError(f"Could not read application icon: {source}")
    images = []
    for size in (256, 128, 64, 48, 32, 16):
        scaled = image.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        color_data = bytearray()
        for y in range(size - 1, -1, -1):
            for x in range(size):
                pixel = scaled.pixelColor(x, y)
                color_data.extend((pixel.blue(), pixel.green(), pixel.red(), pixel.alpha()))
        mask = bytes(((size + 31) // 32) * 4 * size)
        dib = struct.pack(
            "<IIIHHIIIIII",
            40,
            size,
            size * 2,
            1,
            32,
            0,
            len(color_data),
            0,
            0,
            0,
            0,
        ) + color_data + mask
        images.append((size, dib))
    header_size = 6 + 16 * len(images)
    entries = bytearray()
    image_data = bytearray()
    offset = header_size
    for size, dib in images:
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,
                0,
                1,
                32,
                len(dib),
                offset,
            )
        )
        image_data.extend(dib)
        offset += len(dib)
    icon_path = ROOT / "icon.ico"
    icon_path.write_bytes(
        struct.pack("<HHH", 0, 1, len(images)) + entries + image_data
    )
    return icon_path


def _runtime_distributions():
    packages = {}
    stack = list(RUNTIME_PACKAGES) + ["pyinstaller"]
    while stack:
        dist = distribution(stack.pop())
        name = dist.metadata["Name"].lower().replace("_", "-")
        if name in packages:
            continue
        packages[name] = dist
        for raw_requirement in dist.metadata.get_all("Requires-Dist") or ():
            try:
                requirement = Requirement(raw_requirement)
                if requirement.marker is None or requirement.marker.evaluate(
                    {"extra": "", "sys_platform": sys.platform}
                ):
                    stack.append(requirement.name)
            except Exception:
                continue
    return dict(sorted(packages.items()))


def _license_label(dist) -> str:
    value = dist.metadata.get("License")
    if value and value not in ("UNKNOWN", "None"):
        return value.replace("\n", " ").strip()
    classifiers = [
        classifier.split("::", 1)[1].strip()
        for classifier in dist.metadata.get_all("Classifier") or ()
        if classifier.startswith("License ::")
    ]
    return "; ".join(classifiers) if classifiers else "See bundled license files"


def _upstream_url(dist) -> str:
    urls = dist.metadata.get_all("Project-URL") or ()
    for item in urls:
        label, _, url = item.partition(",")
        if any(word in label.lower() for word in ("source", "repository", "homepage")):
            return url.strip()
    return f"https://pypi.org/project/{dist.metadata['Name']}/{dist.version}/"


def _copy_dependency_licenses(destination: Path) -> tuple[str, list[str]]:
    packages = _runtime_distributions()
    entries = []
    source_entries = []
    for normalized_name, dist in packages.items():
        name = dist.metadata["Name"]
        version = dist.version
        entries.append(
            f"| {name} | {version} | {_license_label(dist)} | "
            f"[upstream]({_upstream_url(dist)}) |"
        )
        source_entries.append(
            f"- {name} {version}: {_upstream_url(dist)}"
        )
        candidates = []
        for item in dist.files or ():
            filename = Path(str(item)).name.lower()
            if (
                "license" in filename
                or "copying" in filename
                or filename.startswith("notice")
            ):
                candidates.append(item)
        package_dir = destination / f"{name}-{version}"
        for item in candidates:
            source = dist.locate_file(item)
            if not source.is_file():
                continue
            package_dir.mkdir(parents=True, exist_ok=True)
            target = package_dir / Path(str(item)).name
            if not target.exists():
                shutil.copy2(source, target)
        if name == "PyQt6" and not candidates:
            (destination / "GPL-3.0.txt").write_bytes(
                (ROOT / "installer" / "licenses" / "GPL-3.0.txt").read_bytes()
            )
    return "\n".join(entries), source_entries


def _build_source_bundle(source_dir: Path, packages: dict[str, str]) -> None:
    include_paths = (
        "ads",
        "app",
        "installer",
        "licensing",
        "localization",
        "pdf",
        "scripts",
        "security",
        "storage",
        "translation",
        "tools",
        "ui",
        "workers",
    )
    source_snapshot = source_dir / "ParaLate-source"
    source_snapshot.mkdir(parents=True)
    for relative in include_paths:
        shutil.copytree(
            ROOT / relative,
            source_snapshot / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for relative in (
        "main.py",
        "ParaLate.spec",
        "requirements.txt",
        "requirements-dev.txt",
        "README.md",
        "LICENSE",
        "icon.png",
        "icon.ico",
    ):
        source = ROOT / relative
        if source.is_file():
            shutil.copy2(source, source_snapshot / relative)
    lock = "\n".join(f"{dist.metadata['Name']}=={dist.version}" for dist in packages.values())
    (source_snapshot / "requirements-lock-windows.txt").write_text(
        lock + "\n", encoding="utf-8"
    )

    archive = source_dir / "ParaLate-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in source_snapshot.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(source_dir))
    shutil.rmtree(source_snapshot)


def _make_release_folder() -> None:
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    (RELEASE_DIR / "Source").mkdir(parents=True)
    (RELEASE_DIR / "ThirdPartyLicenses").mkdir()

    license_dir = RELEASE_DIR / "ThirdPartyLicenses"
    for path in (ROOT / "installer" / "licenses").iterdir():
        if path.is_file():
            shutil.copy2(path, license_dir / path.name)
    shutil.copy2(
        ROOT / "installer" / "THIRD_PARTY_NOTICES.md",
        license_dir / "THIRD_PARTY_NOTICES.md",
    )
    inventory, sources = _copy_dependency_licenses(license_dir / "packages")
    (license_dir / "PACKAGE_INVENTORY.md").write_text(
        "# Bundled package inventory\n\n"
        "| Package | Version | Declared license | Upstream/source |\n"
        "|---|---:|---|---|\n"
        f"{inventory}\n",
        encoding="utf-8",
    )
    (RELEASE_DIR / "Source" / "SOURCE_CODE.md").write_text(
        "# ParaLate source code\n\n"
        "The matching ParaLate source snapshot and Windows dependency lock are "
        "in `ParaLate-source.zip`.\n\n"
        "Upstream source locations for the bundled Python components:\n\n"
        + "\n".join(sources)
        + "\n\nThe release's third-party license texts and exact package "
        "inventory are in `../ThirdPartyLicenses`. Qt source and notices are "
        "available from the upstream Qt source archive at "
        "https://download.qt.io/official_releases/qt/.\n",
        encoding="utf-8",
    )
    _build_source_bundle(RELEASE_DIR / "Source", _runtime_distributions())


def main() -> None:
    if os.name != "nt":
        raise SystemExit("This release builder creates Windows executables and must run on Windows.")
    icon = _write_icon()
    for path in (APP_DIST, SETUP_DIST):
        if path.exists():
            shutil.rmtree(path)
    APP_DIST.mkdir(parents=True)
    SETUP_DIST.mkdir(parents=True)

    _run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(APP_DIST),
        "--workpath",
        str(BUILD_ROOT / "app-work"),
        str(ROOT / "ParaLate.spec"),
    )
    app_payload = APP_DIST / "ParaLate"
    if not (app_payload / "ParaLate.exe").is_file():
        raise RuntimeError("PyInstaller did not produce the ParaLate application.")

    _run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(SETUP_DIST),
        "--workpath",
        str(BUILD_ROOT / "setup-work"),
        str(ROOT / "installer" / "Setup.spec"),
    )
    setup_exe = SETUP_DIST / "Setup.exe"
    if not setup_exe.is_file():
        raise RuntimeError("PyInstaller did not produce Setup.exe.")

    _make_release_folder()
    shutil.copy2(setup_exe, RELEASE_DIR / "Setup.exe")
    print(f"Release ready: {RELEASE_DIR}")
    for path in sorted(RELEASE_DIR.iterdir()):
        print(f"  {path.name}{'/' if path.is_dir() else ''}")
    print(f"Setup size: {setup_exe.stat().st_size:,} bytes")
    print(f"Icon generated from: {ROOT / 'icon.png'}")


if __name__ == "__main__":
    main()
