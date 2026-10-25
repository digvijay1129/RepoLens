import { describe, expect, it } from "vitest";
import { normalizeGitHubRepositoryUrl } from "./githubRepository.js";

describe("normalizeGitHubRepositoryUrl", () => {
  it("normalizes a standard GitHub repository URL", () => {
    expect(normalizeGitHubRepositoryUrl("https://github.com/digvijay1129/RepoLens")).toEqual({
      owner: "digvijay1129",
      repository: "RepoLens",
      canonicalUrl: "https://github.com/digvijay1129/RepoLens",
    });
  });

  it("trims whitespace, trailing slash, and an optional .git suffix", () => {
    expect(normalizeGitHubRepositoryUrl("  https://github.com/digvijay1129/RepoLens.git/  ")).toEqual({
      owner: "digvijay1129",
      repository: "RepoLens",
      canonicalUrl: "https://github.com/digvijay1129/RepoLens",
    });
  });

  it.each([
    "",
    "not a url",
    "http://github.com/owner/repo",
    "https://github.com.evil.test/owner/repo",
    "https://github.com/owner/repo/issues",
    "https://github.com/owner/repo?tab=readme",
    "https://github.com/owner/repo#readme",
    "https://user@github.com/owner/repo",
    "https://github.com/owner/%2Frepo",
  ])("rejects invalid repository URLs: %s", (input) => {
    expect(() => normalizeGitHubRepositoryUrl(input)).toThrow();
  });
});
