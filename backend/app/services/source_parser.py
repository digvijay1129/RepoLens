"""Safe, deterministic source-file filtering and line-aware chunking.

Parsing is deliberately non-executing. RepoLens treats repository files as untrusted
text: it never imports, evaluates, runs, or shells out to code fetched from GitHub.
"""

from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath

MAX_CHUNK_CHARS = 4000
CHUNK_OVERLAP_CHARS = 350

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".jsonc": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "text",
    ".md": "markdown",
    ".mdx": "markdown",
    ".rst": "restructuredtext",
    ".txt": "text",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".xml": "xml",
    ".xsd": "xml",
    ".properties": "properties",
    ".gradle": "groovy",
    ".groovy": "groovy",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".proto": "protobuf",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".dockerfile": "dockerfile",
    ".make": "makefile",
}

SUPPORTED_EXTENSIONLESS_NAMES = {
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "justfile": "makefile",
    "dockerfile": "dockerfile",
    "license": "text",
    "notice": "text",
    "authors": "text",
    "contributors": "text",
}

IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".next",
    ".nuxt",
    "target",
    "out",
    "artifacts",
    "site-packages",
    ".idea",
    ".vscode-test",
}

IGNORED_FILENAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "poetry.lock",
    "pipfile.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "flake.lock",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "service-account.json",
    "secrets.json",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "known_hosts",
}

IGNORED_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
    ".jks",
    ".crt",
    ".cer",
    ".der",
    ".sqlite",
    ".db",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".class",
    ".jar",
    ".zip",
    ".gz",
    ".tar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".mp3",
    ".mp4",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".map",
}

SENSITIVE_PATH_SEGMENTS = {
    ".aws",
    ".ssh",
    "secrets",
    "private",
    "credentials",
}


def language_for_path(file_path: str) -> str:
    """Infer a safe display language label from the file name only."""
    path = PurePosixPath(file_path)
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[suffix]
    return SUPPORTED_EXTENSIONLESS_NAMES.get(path.name.lower(), "text")


def is_indexable_path(file_path: str) -> bool:
    """Return whether a path is suitable for source indexing.

    Paths are repository-relative Git tree paths, never filesystem paths. The
    policy excludes likely credentials, generated/vendor trees, lock files,
    binary artifacts, and unsupported file types.
    """
    if (
        not isinstance(file_path, str)
        or not file_path
        or len(file_path) > 1024
        or file_path.startswith("/")
        or chr(92) in file_path
        or chr(0) in file_path
        or any(ord(character) < 32 or ord(character) == 127 for character in file_path)
    ):
        return False

    path = PurePosixPath(file_path)
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return False

    lowered_parts = [part.casefold() for part in parts]
    if any(part in IGNORED_DIRECTORY_NAMES for part in lowered_parts):
        return False
    if any(part in SENSITIVE_PATH_SEGMENTS for part in lowered_parts[:-1]):
        return False

    name = path.name.casefold()
    if name in IGNORED_FILENAMES:
        return False
    if name.startswith(".env"):
        return False
    if name.startswith("id_rsa.") or name.startswith("id_ed25519."):
        return False
    if any(name.endswith(suffix) for suffix in IGNORED_SUFFIXES):
        return False

    # For compound dotfiles, extensionless known documentation/config files
    # are allowed; unknown dotfiles are skipped by default.
    if name.startswith(".") and path.suffix == "":
        return name in SUPPORTED_EXTENSIONLESS_NAMES

    return (
        path.suffix.casefold() in SUPPORTED_EXTENSIONS
        or name in SUPPORTED_EXTENSIONLESS_NAMES
    )


def _line_at_offset(text: str, offset: int) -> int:
    """Map a zero-based character offset to a one-based source line."""
    return text.count("\n", 0, max(0, offset)) + 1



def extract_source_symbols(file_path: str, source_text: str) -> list[dict[str, str | int]]:
    """Extract basic symbol names and line spans without executing repository code.

    Python files are parsed with the standard-library AST. Other common language
    files use conservative declaration patterns. Syntax errors fall back to text
    chunks instead of failing the whole repository job.
    """
    language = language_for_path(file_path)
    symbols: list[dict[str, str | int]] = []

    if language == "python":
        try:
            tree = ast.parse(source_text)
        except (SyntaxError, ValueError, TypeError):
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.append({
                        "name": node.name,
                        "start_line": int(getattr(node, "lineno", 1)),
                        "end_line": int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
                    })
            symbols.sort(key=lambda item: (int(item["start_line"]), str(item["name"])))
            return symbols

    pattern = re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:public\s+)?"
        r"(?:async\s+)?(?:function|class|interface|type|enum|def|func|fn|"
        r"struct|trait|record|namespace|module)\s+([A-Za-z_$][\w$]*)",
        re.MULTILINE,
    )
    for match in pattern.finditer(source_text):
        start_line = source_text.count("\n", 0, match.start()) + 1
        symbols.append({
            "name": match.group(1),
            "start_line": start_line,
            "end_line": start_line,
        })
    return symbols


def chunk_source_text(
    file_path: str,
    source_text: str,
    *,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[dict[str, str | int | list[str]]]:
    """Split source into bounded, overlapping chunks with original line ranges."""
    if not isinstance(source_text, str):
        raise TypeError("Source content must be decoded text.")
    if not source_text.strip():
        return []
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256.")
    if overlap_chars < 0 or overlap_chars >= max_chars // 2:
        raise ValueError("overlap_chars must be non-negative and smaller than half max_chars.")

    language = language_for_path(file_path)
    symbols = extract_source_symbols(file_path, source_text)
    output: list[dict[str, str | int | list[str]]] = []
    start = 0
    text_length = len(source_text)

    while start < text_length:
        hard_end = min(start + max_chars, text_length)
        end = hard_end
        if hard_end < text_length:
            # Prefer a line boundary in the latter part of the window; if no
            # newline is available, fall back to a whitespace boundary.
            floor = start + int(max_chars * 0.65)
            newline_at = source_text.rfind("\n", floor, hard_end)
            space_at = source_text.rfind(" ", floor, hard_end)
            boundary = max(newline_at, space_at)
            if boundary > start:
                end = boundary + 1

        text_chunk = source_text[start:end].strip()
        if text_chunk:
            chunk_start_line = _line_at_offset(source_text, start)
            chunk_end_line = _line_at_offset(source_text, max(start, end - 1))
            chunk_symbols = [
                str(symbol["name"])
                for symbol in symbols
                if int(symbol["start_line"]) <= chunk_end_line
                and int(symbol["end_line"]) >= chunk_start_line
            ]
            output.append(
                {
                    "file_path": file_path,
                    "language": language,
                    "chunk_index": len(output),
                    "start_line": chunk_start_line,
                    "end_line": chunk_end_line,
                    "chunk_text": text_chunk,
                    "symbol_names": chunk_symbols,
                }
            )

        if end >= text_length:
            break

        next_start = max(start + 1, end - overlap_chars)
        # When possible, begin the next chunk just after a line break while
        # keeping the overlap bounded and deterministic.
        newline_at = source_text.find("\n", next_start, end)
        if newline_at >= 0:
            next_start = newline_at + 1
        start = next_start

    return output
