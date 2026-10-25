"""Bounded source retrieval helpers using RepoLens' fixed-host GitHub client."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any
from urllib.parse import quote

from app.services.github_client import (
    GitHubClientError,
    GitHubPublicClient,
    validate_repository_locator,
)

MAX_INDEX_TREE_ENTRIES = 30000
MAX_INDEX_FILE_BYTES = 256 * 1024


async def get_commit_tree(
    github: GitHubPublicClient,
    owner: str,
    repository: str,
    commit_sha: str,
) -> list[dict[str, Any]]:
    """Return a bounded recursive Git tree for a validated immutable commit."""
    owner, repository = validate_repository_locator(owner, repository)
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit_sha):
        raise ValueError("The commit reference is invalid.")

    payload = await github._get_json(
        f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/git/trees/"
        f"{quote(commit_sha, safe='')}",
        params={"recursive": "1"},
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("tree"), list):
        raise GitHubClientError(502, "GitHub returned an unexpected repository tree.")
    entries = payload["tree"]
    if payload.get("truncated") or len(entries) > MAX_INDEX_TREE_ENTRIES:
        raise GitHubClientError(
            413,
            "This repository tree is too large to index safely in one pass. "
            "A narrower indexing scope will be supported in a later phase.",
        )

    safe_entries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path, sha, kind = entry.get("path"), entry.get("sha"), entry.get("type")
        if not isinstance(path, str) or not isinstance(sha, str):
            continue
        if kind not in {"blob", "tree", "commit"}:
            continue
        size = entry.get("size")
        safe_entries.append({
            "path": path,
            "sha": sha,
            "type": kind,
            "size": size if isinstance(size, int) and size >= 0 else None,
            "mode": entry.get("mode") if isinstance(entry.get("mode"), str) else None,
        })
    return safe_entries


async def get_blob_text(
    github: GitHubPublicClient,
    owner: str,
    repository: str,
    blob_sha: str,
    *,
    max_bytes: int = MAX_INDEX_FILE_BYTES,
) -> str:
    """Read a bounded Git blob and decode UTF-8 without executing repository code."""
    owner, repository = validate_repository_locator(owner, repository)
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", blob_sha):
        raise ValueError("The source blob reference is invalid.")
    if max_bytes <= 0 or max_bytes > MAX_INDEX_FILE_BYTES:
        raise ValueError("The source file size limit is invalid.")

    payload = await github._get_json(
        f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/git/blobs/"
        f"{quote(blob_sha, safe='')}"
    )
    if not isinstance(payload, dict):
        raise GitHubClientError(502, "GitHub returned an unexpected source blob.")
    size = payload.get("size")
    if isinstance(size, int) and (size < 0 or size > max_bytes):
        raise GitHubClientError(413, "Source file exceeds the indexing size limit.")

    content = payload.get("content")
    if payload.get("encoding") != "base64" or not isinstance(content, str):
        raise GitHubClientError(415, "Source file is not available as plain text.")
    compact = "".join(content.split())
    if len(compact) > ((max_bytes + 2) // 3) * 4 + 8:
        raise GitHubClientError(413, "Source file exceeds the indexing size limit.")
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GitHubClientError(502, "GitHub returned an invalid source blob.") from exc
    if len(decoded) > max_bytes:
        raise GitHubClientError(413, "Source file exceeds the indexing size limit.")
    try:
        text = decoded.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GitHubClientError(415, "Non-UTF-8 files are not indexed.") from exc
    if chr(0) in text:
        raise GitHubClientError(415, "Binary files are not indexed.")
    return text
