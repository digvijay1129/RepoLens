"""Build a clean, source-only RepoLens release ZIP without local secrets or dependencies."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = "RepoLens"
EXCLUDED_DIRECTORIES = {
    ".git", ".venv", "venv", "ENV", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".vite", ".vitest",
    "coverage", ".coverage", "htmlcov", "dist", "build", ".idea", ".vscode",
    ".next", ".turbo", ".nyc_output",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".sqlite", ".sqlite3"}
REQUIRED_ARCHIVE_PATHS = {
    "RepoLens/README.md",
    "RepoLens/SECURITY.md",
    "RepoLens/backend/.env.example",
    "RepoLens/frontend/.env.example",
    "RepoLens/backend/app/main.py",
    "RepoLens/backend/migrations/versions/20261025_0007_rag_chat_history.py",
    "RepoLens/backend/app/evaluation/evaluate.py",
    "RepoLens/docs/PHASE_8.md",
    "RepoLens/scripts/package_release.py",
    "RepoLens/.github/workflows/ci.yml",
}


def should_include(path: Path, output_path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return False
    if path.resolve() == output_path:
        return False
    relative = path.relative_to(REPOSITORY_ROOT)
    if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name == ".env":
        return False
    if path.name.startswith(".env.") and path.name != ".env.example":
        return False
    if path.name.endswith((".zip", ".tar.gz", ".tgz")):
        return False
    return True


def validate_archive(archive_path: Path) -> tuple[int, int]:
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        missing = REQUIRED_ARCHIVE_PATHS - names
        if missing:
            raise ValueError("Release archive is missing required files: " + ", ".join(sorted(missing)))
        unsafe = []
        for name in names:
            path = PurePosixPath(name)
            if any(part in EXCLUDED_DIRECTORIES for part in path.parts):
                unsafe.append(name)
                continue
            leaf = path.name
            if leaf == ".env" or (leaf.startswith(".env.") and leaf != ".env.example"):
                unsafe.append(name)
            elif leaf.endswith((".pyc", ".pyo", ".log", ".sqlite", ".sqlite3")):
                unsafe.append(name)
        if unsafe:
            raise ValueError("Release archive contains excluded files: " + ", ".join(sorted(unsafe)[:20]))
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError("Release archive contains a corrupt entry: " + corrupt)
        return len(names), archive_path.stat().st_size


def build_archive(output_path: Path) -> tuple[int, int]:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=8,
    ) as archive:
        paths = sorted(REPOSITORY_ROOT.rglob("*"))
        for path in paths:
            if not should_include(path, output_path):
                continue
            relative = path.relative_to(REPOSITORY_ROOT)
            archive_name = (PurePosixPath(TOP_LEVEL) / PurePosixPath(relative.as_posix())).as_posix()
            archive.write(path, archive_name)
    count, size = validate_archive(output_path)
    return count, size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../RepoLens-Phase8-Release.zip"),
        help="Output ZIP path (default: ../RepoLens-Phase8-Release.zip)",
    )
    args = parser.parse_args()
    try:
        count, size = build_archive(args.output)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(f"Release packaging failed: {exc}", file=sys.stderr)
        return 1
    print(f"Release archive: {args.output.expanduser().resolve()}")
    print(f"Entries: {count}")
    print(f"Size: {size:,} bytes")
    print("Archive validation: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
