from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "integrations" / "openclaw-plugin-src"
DIST_DIR = ROOT / "dist" / "openclaw-plugin"
ARCHIVE_STEM = ROOT / "dist" / "social-data-crawler-openclaw-plugin"
# canonical relative roots:
# - integrations/openclaw-plugin-src
# - dist/openclaw-plugin
EXCLUDED_NAMES = {
    ".git",
    ".gitignore",
    ".pytest_cache",
    ".DS_Store",
    "__pycache__",
    "tests",
    "node_modules",
}


def build_plugin_dist() -> list[Path]:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"missing plugin source directory: {SOURCE_DIR}")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    copied_files: list[Path] = []
    for source_path in sorted(SOURCE_DIR.rglob("*")):
        relative_path = source_path.relative_to(SOURCE_DIR)
        if any(part in EXCLUDED_NAMES for part in relative_path.parts):
            continue
        if source_path.is_dir():
            (DIST_DIR / relative_path).mkdir(parents=True, exist_ok=True)
            continue
        target_path = DIST_DIR / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_files.append(target_path)

    manifest = {
        "source": str(SOURCE_DIR),
        "dist": str(DIST_DIR),
        "files": [str(path.relative_to(DIST_DIR)).replace("\\", "/") for path in copied_files],
        "excluded_names": sorted(EXCLUDED_NAMES),
    }
    (DIST_DIR / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    copied_files.append(DIST_DIR / "release-manifest.json")
    return copied_files


def build_archives() -> tuple[Path, Path]:
    zip_path = Path(
        shutil.make_archive(
            str(ARCHIVE_STEM),
            "zip",
            root_dir=str(DIST_DIR.parent),
            base_dir=DIST_DIR.name,
        )
    )
    tar_path = ARCHIVE_STEM.with_suffix(".tar.gz")
    with tarfile.open(tar_path, "w:gz") as handle:
        handle.add(DIST_DIR, arcname=DIST_DIR.name)
    return zip_path, tar_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the minimal OpenClaw plugin distribution bundle.")
    parser.add_argument("--no-archive", action="store_true", help="Skip .zip and .tar.gz archive generation.")
    args = parser.parse_args()

    copied_files = build_plugin_dist()
    print(json.dumps({"dist": str(DIST_DIR), "files": len(copied_files)}, ensure_ascii=False))
    if args.no_archive:
        return 0
    zip_path, tar_path = build_archives()
    print(json.dumps({"zip": str(zip_path), "tar_gz": str(tar_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
