const OWNER_PATTERN = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/;
const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]+$/;

export function normalizeGitHubRepositoryUrl(input) {
  if (typeof input !== "string" || !input.trim()) {
    throw new Error("Enter a GitHub repository URL.");
  }

  let parsed;
  try {
    parsed = new URL(input.trim());
  } catch {
    throw new Error("Enter a valid GitHub repository URL.");
  }

  if (
    parsed.protocol !== "https:" ||
    parsed.hostname.toLowerCase() !== "github.com" ||
    (parsed.port && parsed.port !== "443") ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error("Use a secure GitHub repository URL without query parameters.");
  }

  const pathname = parsed.pathname.endsWith("/")
    ? parsed.pathname.slice(0, -1)
    : parsed.pathname;
  const rawSegments = pathname.split("/").slice(1);

  if (
    !pathname.startsWith("/") ||
    rawSegments.length !== 2 ||
    rawSegments.some((segment) => !segment)
  ) {
    throw new Error("Enter a repository URL with exactly an owner and repository name.");
  }

  let owner;
  let repository;
  try {
    owner = decodeURIComponent(rawSegments[0]);
    repository = decodeURIComponent(rawSegments[1]);
  } catch {
    throw new Error("The repository URL contains invalid encoded characters.");
  }

  repository = repository.replace(/\.git$/i, "");

  if (!OWNER_PATTERN.test(owner)) {
    throw new Error("The GitHub owner name is not valid.");
  }

  if (
    !REPOSITORY_PATTERN.test(repository) ||
    !/[A-Za-z0-9]/.test(repository) ||
    repository.includes("..")
  ) {
    throw new Error("The GitHub repository name is not valid.");
  }

  return {
    owner,
    repository,
    canonicalUrl: `https://github.com/${owner}/${repository}`,
  };
}
