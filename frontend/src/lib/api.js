const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(API_BASE_URL + path, {
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) },
      ...options,
    });
  } catch {
    throw new Error("Cannot reach the RepoLens API. Check that the backend is running.");
  }

  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload && typeof payload.detail === "string" ? payload.detail : "";
    if (response.status === 404) {
      throw new Error(detail || "Public repository or directory was not found.");
    }
    if (response.status === 429) {
      throw new Error(detail || "GitHub's public API rate limit was reached. Please retry later.");
    }
    if (response.status === 422) {
      throw new Error(detail || "The repository URL or path is invalid.");
    }
    if (response.status >= 500) {
      throw new Error(detail || "The repository service is temporarily unavailable. Please retry.");
    }
    throw new Error(detail || "The request could not be completed.");
  }

  if (!payload || typeof payload !== "object") {
    throw new Error("The RepoLens API returned an unexpected response.");
  }
  return payload;
}

export async function getApiHealth() {
  return requestJson("/api/v1/health/live");
}

export async function inspectRepository(repositoryUrl) {
  return requestJson("/api/v1/repositories/inspect", {
    method: "POST",
    body: JSON.stringify({ repository_url: repositoryUrl }),
  });
}

export async function getRepositoryContents(owner, repository, options = {}) {
  const params = new URLSearchParams();
  if (options.path) params.set("path", options.path);
  if (options.ref) params.set("ref", options.ref);
  const query = params.toString();
  const path = "/api/v1/repositories/" + encodeURIComponent(owner) + "/" +
    encodeURIComponent(repository) + "/contents" + (query ? "?" + query : "");
  return requestJson(path);
}

export { API_BASE_URL };
