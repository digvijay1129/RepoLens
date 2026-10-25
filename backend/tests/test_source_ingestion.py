import base64

import httpx
import pytest

from app.services.github_client import GitHubClientError, GitHubPublicClient
from app.services.source_ingestion import get_blob_text, get_commit_tree


@pytest.mark.asyncio
async def test_get_commit_tree_uses_fixed_github_api_and_returns_curated_entries() -> None:
    commit_sha = "a" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        assert request.url.path == f"/repos/owner/repo/git/trees/{commit_sha}"
        assert request.url.params["recursive"] == "1"
        return httpx.Response(
            200,
            json={
                "sha": "tree-sha",
                "truncated": False,
                "tree": [
                    {"path": "src/main.py", "type": "blob", "sha": "b" * 40, "size": 50},
                    {"path": "src", "type": "tree", "sha": "c" * 40},
                    {"path": "ignored", "type": "commit", "sha": "d" * 40},
                ],
            },
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        entries = await get_commit_tree(client, "owner", "repo", commit_sha)

    assert [entry["path"] for entry in entries] == ["src/main.py", "src", "ignored"]
    assert entries[0]["size"] == 50
    assert entries[1]["size"] is None


@pytest.mark.asyncio
async def test_get_commit_tree_rejects_truncated_or_too_large_trees() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"sha": "tree", "truncated": True, "tree": []},
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await get_commit_tree(client, "owner", "repo", "a" * 40)

    assert error.value.status_code == 413
    assert "too large" in error.value.detail


@pytest.mark.asyncio
async def test_get_blob_text_decodes_utf8_and_rejects_binary_or_oversize() -> None:
    raw_text = "def greet(name):\n    return f'Hello {name}'\n"
    encoded = base64.b64encode(raw_text.encode()).decode()

    def good_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"sha": "b" * 40, "size": len(raw_text.encode()), "encoding": "base64", "content": encoded},
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(good_handler)) as client:
        text = await get_blob_text(client, "owner", "repo", "b" * 40)

    assert text == raw_text

    def large_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"size": 999, "encoding": "base64", "content": "QQ=="},
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(large_handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await get_blob_text(client, "owner", "repo", "b" * 40, max_bytes=20)

    assert error.value.status_code == 413

    binary_encoded = base64.b64encode(b"\x00\x01\x02").decode()

    def binary_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"size": 3, "encoding": "base64", "content": binary_encoded},
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(binary_handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await get_blob_text(client, "owner", "repo", "b" * 40)

    assert error.value.status_code == 415
