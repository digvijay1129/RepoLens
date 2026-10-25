const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const ACCESS_TOKEN_KEY = "repolens_access_token";

export function getAccessToken() {
  try {
    return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token) {
  window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken() {
  try {
    window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  } catch {
    // The browser may have storage disabled; sign-out still clears React state.
  }
}

async function requestJson(path, options = {}) {
  let response;
  const headers = {
    Accept: "application/json",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };
  const accessToken = getAccessToken();
  if (accessToken && !headers.Authorization && !headers.authorization) {
    headers.Authorization = "Bearer " + accessToken;
  }

  try {
    response = await fetch(API_BASE_URL + path, { ...options, headers });
  } catch {
    throw new Error("Cannot reach the RepoLens API. Check that the backend is running.");
  }

  let payload;
  try {
    payload = response.status === 204 ? null : await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload && typeof payload.detail === "string" ? payload.detail : "";
    if (response.status === 401) {
      throw new Error(detail || "Your session expired. Please sign in again.");
    }
    if (response.status === 403) {
      throw new Error(detail || "You do not have permission to perform this action.");
    }
    if (response.status === 404) {
      throw new Error(detail || "Public repository or saved record was not found.");
    }
    if (response.status === 409) {
      throw new Error(detail || "An account or repository with these details already exists.");
    }
    if (response.status === 422) {
      throw new Error(detail || "The submitted information is invalid.");
    }
    if (response.status === 429) {
      throw new Error(detail || "GitHub's public API rate limit was reached. Please retry later.");
    }
    if (response.status >= 500) {
      throw new Error(detail || "The RepoLens service is temporarily unavailable. Please retry.");
    }
    throw new Error(detail || "The request could not be completed.");
  }

  if (response.status === 204) return null;
  if (!payload || typeof payload !== "object") {
    throw new Error("The RepoLens API returned an unexpected response.");
  }
  return payload;
}

export async function getApiHealth() {
  return requestJson("/api/v1/health/live");
}

export async function registerAccount(payload) {
  return requestJson("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loginAccount(payload) {
  return requestJson("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUser() {
  return requestJson("/api/v1/auth/me");
}

export async function inspectRepository(repositoryUrl) {
  return requestJson("/api/v1/repositories/inspect", {
    method: "POST",
    body: JSON.stringify({ repository_url: repositoryUrl }),
  });
}

export async function saveRepository(repositoryUrl) {
  return requestJson("/api/v1/repositories/saved", {
    method: "POST",
    body: JSON.stringify({ repository_url: repositoryUrl }),
  });
}

export async function getSavedRepositories() {
  return requestJson("/api/v1/repositories/saved");
}

export async function deleteSavedRepository(repositoryId) {
  return requestJson("/api/v1/repositories/saved/" + encodeURIComponent(repositoryId), {
    method: "DELETE",
  });
}

export async function getRepositoryBranches(repositoryId) {
  return requestJson("/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/branches");
}

export async function selectRepositoryBranch(repositoryId, selectedBranch) {
  return requestJson("/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/branch", {
    method: "PATCH",
    body: JSON.stringify({ selected_branch: selectedBranch }),
  });
}

export async function startRepositoryIndex(repositoryId) {
  return requestJson("/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/index", {
    method: "POST",
  });
}

export async function startRepositoryEmbeddings(repositoryId) {
  return requestJson("/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/embeddings", {
    method: "POST",
  });
}

export async function getRepositoryIndexingJob(repositoryId, jobId) {
  return requestJson(
    "/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) +
    "/jobs/" + encodeURIComponent(jobId),
  );
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


export async function searchSavedRepository(repositoryId, payload) {
  return requestJson(
    "/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/search",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}


export async function chatWithSavedRepository(repositoryId, payload) {
  return requestJson(
    "/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/chat",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getRepositoryConversations(repositoryId) {
  return requestJson(
    "/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) + "/conversations",
  );
}

export async function getRepositoryConversation(repositoryId, conversationId) {
  return requestJson(
    "/api/v1/repositories/saved/" + encodeURIComponent(repositoryId) +
    "/conversations/" + encodeURIComponent(conversationId),
  );
}
