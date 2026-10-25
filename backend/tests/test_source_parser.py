from app.services.source_parser import (
    chunk_source_text,
    is_indexable_path,
    language_for_path,
)


def test_supported_source_paths_are_detected() -> None:
    assert is_indexable_path("backend/app/main.py")
    assert is_indexable_path("frontend/src/App.jsx")
    assert is_indexable_path("README.md")
    assert is_indexable_path(".github/workflows/ci.yml")
    assert language_for_path("backend/app/main.py") == "python"
    assert language_for_path("frontend/src/App.jsx") == "javascript"


def test_credentials_generated_directories_binaries_and_lockfiles_are_excluded() -> None:
    paths = [
        ".env",
        ".env.example",
        "backend/.aws/credentials",
        "secrets/service.json",
        "id_rsa",
        "certs/server.pem",
        "node_modules/react/index.js",
        "target/classes/Main.java",
        "package-lock.json",
        "dist/assets/app.js",
        "assets/logo.png",
        "unknown/file.custom",
        "../outside.py",
        "/absolute/path.py",
        "backend\\private.py",
    ]
    assert all(not is_indexable_path(path) for path in paths)


def test_chunking_is_bounded_line_aware_and_deterministic() -> None:
    source = "".join(
        f"def function_{index}():\n    return 'value-{index}'\n"
        for index in range(250)
    )

    first = chunk_source_text("src/module.py", source, max_chars=900, overlap_chars=100)
    second = chunk_source_text("src/module.py", source, max_chars=900, overlap_chars=100)

    assert len(first) > 1
    assert first == second
    assert all(len(chunk["chunk_text"]) <= 900 for chunk in first)
    assert [chunk["chunk_index"] for chunk in first] == list(range(len(first)))
    assert all(chunk["start_line"] >= 1 for chunk in first)
    assert all(chunk["end_line"] >= chunk["start_line"] for chunk in first)
    assert first[0]["chunk_text"].startswith("def function_0()")
    assert first[-1]["chunk_text"].endswith("return 'value-249'")
    assert "function_0" in first[0]["symbol_names"]


def test_empty_text_produces_no_chunks_and_invalid_limits_are_rejected() -> None:
    assert chunk_source_text("README.md", "  \n  ") == []
    try:
        chunk_source_text("README.md", "some text", max_chars=10)
    except ValueError as exc:
        assert "at least 256" in str(exc)
    else:
        raise AssertionError("Invalid chunk limits should raise ValueError")
