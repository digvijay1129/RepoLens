import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearAccessToken,
  deleteSavedRepository,
  getRepositoryBranches,
  getRepositoryContents,
  getRepositoryIndexingJob,
  getSavedRepositories,
  inspectRepository,
  loginAccount,
  registerAccount,
  saveRepository,
  selectRepositoryBranch,
  startRepositoryIndex,
  startRepositoryEmbeddings,
  searchSavedRepository,
  chatWithSavedRepository,
  getRepositoryConversations,
  getRepositoryConversation,
  setAccessToken,
} from "./api.js";

afterEach(() => {
  vi.unstubAllGlobals();
  clearAccessToken();
});

describe("RepoLens API client", () => {
  it("posts account registration and login payloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ access_token: "signed-token", user: { email: "dev@example.com" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await registerAccount({ email: "dev@example.com", password: "a-strong-password-2026" });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/auth\/register$/),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("posts a canonical public repository URL to the inspect endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ full_name: "owner/repo", private: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await inspectRepository("https://github.com/owner/repo");

    expect(result.full_name).toBe("owner/repo");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/repositories\/inspect$/),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ repository_url: "https://github.com/owner/repo" }),
      }),
    );
  });

  it("attaches the session bearer token to protected API calls", async () => {
    setAccessToken("signed-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    await getSavedRepositories();

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer signed-token");
  });

  it("encodes directory and ref query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], path: "src files" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getRepositoryContents("my-org", "my-repo", {
      path: "src files",
      ref: "feature/first",
    });

    const requestedUrl = new URL(fetchMock.mock.calls[0][0]);
    expect(requestedUrl.pathname).toBe("/api/v1/repositories/my-org/my-repo/contents");
    expect(requestedUrl.searchParams.get("path")).toBe("src files");
    expect(requestedUrl.searchParams.get("ref")).toBe("feature/first");
  });

  it("supports persistent repository actions and branch selection", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: "repo-1" }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ items: [] }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ selected_branch: "feature/a" }) })
      .mockResolvedValueOnce({ ok: true, status: 204, json: async () => null });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("signed-token");

    await saveRepository("https://github.com/owner/repo");
    await getRepositoryBranches("repo-1");
    await selectRepositoryBranch("repo-1", "feature/a");
    await deleteSavedRepository("repo-1");

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/repositories\/saved$/);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/repositories\/saved\/repo-1\/branches$/);
    expect(fetchMock.mock.calls[2][1].method).toBe("PATCH");
    expect(fetchMock.mock.calls[3][1].method).toBe("DELETE");
  });

  it("uses a safe message when the backend is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network detail")));

    await expect(inspectRepository("https://github.com/owner/repo")).rejects.toThrow(
      /Cannot reach the RepoLens API/,
    );
  });

  it("surfaces a sanitized backend detail for not-found responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Public GitHub repository or path was not found." }),
    }));

    await expect(getRepositoryContents("owner", "missing")).rejects.toThrow(/not found/i);
  });
});


  it("starts indexing and reads the owner-scoped job progress endpoint", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({ id: "job-1", status: "queued" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: "job-1", status: "completed", chunk_count: 11 }),
      });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("signed-token");

    const queued = await startRepositoryIndex("repo-1");
    const completed = await getRepositoryIndexingJob("repo-1", queued.id);

    expect(queued.status).toBe("queued");
    expect(completed.chunk_count).toBe(11);
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/repositories\/saved\/repo-1\/index$/);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/repositories\/saved\/repo-1\/jobs\/job-1$/);
  });



  it("starts owner-scoped embedding generation for a saved repository", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({
        id: "embedding-job",
        job_type: "embedding",
        status: "queued",
        embedding_provider: "openai_compatible",
        embedding_model: "text-embedding-3-small",
        embedding_dimensions: 1536,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("signed-token");

    const job = await startRepositoryEmbeddings("repo-1");

    expect(job.job_type).toBe("embedding");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/repositories\/saved\/repo-1\/embeddings$/);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer signed-token");
  });


  it("searches a saved repository with the selected retrieval mode", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        repository_id: "repo-1",
        repository: "org/repo",
        query: "auth handler",
        mode: "hybrid",
        commit_sha: "a".repeat(40),
        result_count: 0,
        results: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("signed-token");
    const result = await searchSavedRepository("repo-1", {
      query: "auth handler",
      mode: "hybrid",
      limit: 8,
    });
    expect(result.mode).toBe("hybrid");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/repositories\/saved\/repo-1\/search$/);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      query: "auth handler", mode: "hybrid", limit: 8,
    });
  });


  it("creates repository chat turns and loads saved conversation history", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: "conversation-1", answer: "Grounded answer [S1]." }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [{ id: "conversation-1", title: "Auth flow" }] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: "conversation-1", messages: [] }),
      });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("signed-token");

    await chatWithSavedRepository("repo-1", { message: "Explain authentication" });
    const conversations = await getRepositoryConversations("repo-1");
    const history = await getRepositoryConversation("repo-1", "conversation-1");

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/repositories\/saved\/repo-1\/chat$/);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ message: "Explain authentication" });
    expect(conversations.items[0].title).toBe("Auth flow");
    expect(history.id).toBe("conversation-1");
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/repositories\/saved\/repo-1\/conversations$/);
    expect(fetchMock.mock.calls[2][0]).toMatch(/\/repositories\/saved\/repo-1\/conversations\/conversation-1$/);
  });
