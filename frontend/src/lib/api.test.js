import { afterEach, describe, expect, it, vi } from "vitest";
import { getRepositoryContents, inspectRepository } from "./api.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RepoLens repository API client", () => {
  it("posts a canonical public repository URL to the backend", async () => {
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
