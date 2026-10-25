import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App.jsx";

import {
  clearAccessToken,
  getAccessToken,
  getApiHealth,
  getCurrentUser,
  getRepositoryBranches,
  getRepositoryContents,
  getRepositoryIndexingJob,
  getSavedRepositories,
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
  deleteSavedRepository,
} from "./lib/api.js";

vi.mock("./lib/api.js", () => ({
  clearAccessToken: vi.fn(() => window.sessionStorage.removeItem("repolens_access_token")),
  getAccessToken: vi.fn(() => window.sessionStorage.getItem("repolens_access_token")),
  setAccessToken: vi.fn((token) => window.sessionStorage.setItem("repolens_access_token", token)),
  getApiHealth: vi.fn(),
  getCurrentUser: vi.fn(),
  getRepositoryBranches: vi.fn(),
  getRepositoryContents: vi.fn(),
  getRepositoryIndexingJob: vi.fn(),
  getSavedRepositories: vi.fn(),
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
  saveRepository: vi.fn(),
  selectRepositoryBranch: vi.fn(),
  startRepositoryIndex: vi.fn(),
  startRepositoryEmbeddings: vi.fn(),
  searchSavedRepository: vi.fn(),
  chatWithSavedRepository: vi.fn(),
  getRepositoryConversations: vi.fn(),
  getRepositoryConversation: vi.fn(),
  deleteSavedRepository: vi.fn(),
}));

const userProfile = {
  id: "user-123",
  email: "developer@example.com",
  display_name: "Developer",
  is_active: true,
};

const repository = {
  id: "repository-123",
  github_repository_id: 123,
  name: "RepoLens",
  github_owner: "digvijay1129",
  github_name: "RepoLens",
  full_name: "digvijay1129/RepoLens",
  canonical_url: "https://github.com/digvijay1129/RepoLens",
  html_url: "https://github.com/digvijay1129/RepoLens",
  description: "GitHub codebase intelligence",
  default_branch: "main",
  selected_branch: "main",
  language: "Python",
  stargazers_count: 2,
  forks_count: 1,
  open_issues_count: 1,
  size: 200,
  license_name: "MIT License",
  archived: false,
  indexing_status: "pending",
  embedding_status: "pending",
  embedding_provider: null,
  embedding_model: null,
  embedding_dimensions: null,
  github_updated_at: "2026-10-25T00:00:00Z",
  created_at: "2026-10-25T00:00:00Z",
  updated_at: "2026-10-25T00:00:00Z",
};

const directory = {
  full_name: "digvijay1129/RepoLens",
  owner: "digvijay1129",
  repository: "RepoLens",
  path: "",
  ref: "main",
  items: [
    {
      name: "backend",
      path: "backend",
      type: "dir",
      sha: "abc123",
      size: null,
      html_url: "https://github.com/digvijay1129/RepoLens/tree/main/backend",
      download_url: null,
    },
    {
      name: "README.md",
      path: "README.md",
      type: "file",
      sha: "def456",
      size: 100,
      html_url: "https://github.com/digvijay1129/RepoLens/blob/main/README.md",
      download_url: null,
    },
  ],
  may_be_truncated: false,
  notice: null,
};

describe("RepoLens authenticated workspace and repository browsing", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    window.sessionStorage.clear();
    setAccessToken("test-access-token");
    getApiHealth.mockResolvedValue({ status: "ok" });
    getCurrentUser.mockResolvedValue(userProfile);
    getSavedRepositories.mockResolvedValue([]);
    getRepositoryConversations.mockResolvedValue({ repository_id: repository.id, items: [] });
    getRepositoryConversation.mockResolvedValue({ id: "conversation-1", repository_id: repository.id, title: "Saved chat", messages: [] });
    chatWithSavedRepository.mockResolvedValue({
      id: "conversation-1",
      repository_id: repository.id,
      title: "How is authentication validated?",
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:01Z",
      answer: "Token validation is delegated to authenticate_user [S1].",
      retrieval_mode: "keyword",
      commit_sha: "a".repeat(40),
      sources: [{
        id: "S1",
        file_path: "backend/app/auth.py",
        language: "python",
        start_line: 12,
        end_line: 28,
        symbol_names: ["authenticate_user"],
        score: 1,
        match_types: ["keyword"],
        commit_sha: "a".repeat(40),
        citation_url: "https://github.com/digvijay1129/RepoLens/blob/" + "a".repeat(40) + "/backend/app/auth.py#L12-L28",
      }],
      user_message: {
        id: "message-user-1",
        conversation_id: "conversation-1",
        role: "user",
        content: "How is authentication validated?",
        sources: [],
        created_at: "2026-10-25T00:00:00Z",
      },
      assistant_message: {
        id: "message-assistant-1",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "Token validation is delegated to authenticate_user [S1].",
        sources: [{
          id: "S1",
          file_path: "backend/app/auth.py",
          language: "python",
          start_line: 12,
          end_line: 28,
          symbol_names: ["authenticate_user"],
          score: 1,
          match_types: ["keyword"],
          commit_sha: "a".repeat(40),
          citation_url: "https://github.com/digvijay1129/RepoLens/blob/" + "a".repeat(40) + "/backend/app/auth.py#L12-L28",
        }],
        created_at: "2026-10-25T00:00:01Z",
      },
    });
    getRepositoryBranches.mockResolvedValue({
      repository_id: repository.id,
      selected_branch: "main",
      default_branch: "main",
      items: [
        { name: "main", commit_sha: "a".repeat(40), protected: true },
        { name: "feature/add-tests", commit_sha: "b".repeat(40), protected: false },
      ],
      may_be_truncated: false,
    });
    getRepositoryContents.mockResolvedValue(directory);
    getRepositoryIndexingJob.mockResolvedValue({
      id: "job-123",
      repository_id: repository.id,
      job_type: "source_indexing",
      embedding_provider: null,
      embedding_model: null,
      embedding_dimensions: null,
      status: "completed",
      attempt_count: 1,
      total_files: 1,
      processed_files: 1,
      skipped_files: 3,
      chunk_count: 5,
      commit_sha: "a".repeat(40),
      progress_message: "Indexing completed successfully.",
      error_message: null,
      started_at: "2026-10-25T00:00:00Z",
      finished_at: "2026-10-25T00:00:05Z",
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:05Z",
    });
    startRepositoryIndex.mockResolvedValue({
      id: "job-123",
      repository_id: repository.id,
      job_type: "source_indexing",
      embedding_provider: null,
      embedding_model: null,
      embedding_dimensions: null,
      status: "completed",
      attempt_count: 1,
      total_files: 1,
      processed_files: 1,
      skipped_files: 3,
      chunk_count: 5,
      commit_sha: "a".repeat(40),
      progress_message: "Indexing completed successfully.",
      error_message: null,
      started_at: "2026-10-25T00:00:00Z",
      finished_at: "2026-10-25T00:00:05Z",
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:05Z",
    });
    saveRepository.mockResolvedValue(repository);
    selectRepositoryBranch.mockImplementation(async (_id, selectedBranch) => ({
      ...repository,
      selected_branch: selectedBranch,
    }));
    deleteSavedRepository.mockResolvedValue(null);
    loginAccount.mockResolvedValue({ access_token: "login-token", user: userProfile });
    registerAccount.mockResolvedValue({ access_token: "register-token", user: userProfile });
    searchSavedRepository.mockResolvedValue({
      repository_id: repository.id,
      repository: "digvijay1129/repolens",
      query: "authenticate_user",
      mode: "keyword",
      commit_sha: "a".repeat(40),
      result_count: 1,
      results: [{
        chunk_id: "chunk-1",
        file_path: "backend/app/auth.py",
        language: "python",
        start_line: 12,
        end_line: 28,
        symbol_names: ["authenticate_user"],
        snippet: "def authenticate_user(token): return user",
        score: 1,
        match_types: ["keyword"],
        commit_sha: "a".repeat(40),
        citation_url: "https://github.com/digvijay1129/RepoLens/blob/" + "a".repeat(40) + "/backend/app/auth.py#L12-L28",
      }],
    });
    startRepositoryEmbeddings.mockResolvedValue({
      id: "embedding-job-1",
      repository_id: repository.id,
      job_type: "embedding",
      embedding_provider: "openai_compatible",
      embedding_model: "test-embedding-model",
      embedding_dimensions: 3,
      status: "completed",
      attempt_count: 1,
      total_files: 1,
      processed_files: 1,
      skipped_files: 0,
      chunk_count: 1,
      commit_sha: "a".repeat(40),
      progress_message: "Generated 1 embeddings with openai_compatible/test-embedding-model.",
      error_message: null,
      started_at: "2026-10-25T00:00:00Z",
      finished_at: "2026-10-25T00:00:05Z",
      created_at: "2026-10-25T00:00:00Z",
      updated_at: "2026-10-25T00:00:05Z",
    });
  });

  afterEach(() => {
    clearAccessToken();
    vi.clearAllMocks();
  });

  it("shows the sign-in experience when no session token exists", async () => {
    clearAccessToken();
    render(<App />);

    expect(await screen.findByRole("heading", { name: /sign in to repolens/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /email address/i })).toBeInTheDocument();
    expect(screen.queryByText("Recent repositories")).not.toBeInTheDocument();
  });

  it("authenticates and restores the persistent workspace", async () => {
    clearAccessToken();
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByRole("textbox", { name: /email address/i }), "developer@example.com");
    await user.type(screen.getByLabelText(/password/i), "a-strong-test-password");
    await user.click(screen.getByRole("button", { name: /submit sign in/i }));

    expect(await screen.findByText("Recent repositories")).toBeInTheDocument();
    expect(loginAccount).toHaveBeenCalledWith({
      email: "developer@example.com",
      password: "a-strong-test-password",
    });
    expect(setAccessToken).toHaveBeenCalledWith("login-token");
    expect(getSavedRepositories).toHaveBeenCalled();
  });

  it("renders the dashboard and API status", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: /your code workspace/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /connect repository/i })).toBeInTheDocument();
    expect(await screen.findByText("Recent repositories")).toBeInTheDocument();
    expect(await screen.findByText("API online")).toBeInTheDocument();
    expect(screen.getAllByText("developer@example.com").length).toBeGreaterThanOrEqual(1);
  });

  it("shows an offline state when the backend health request fails", async () => {
    getApiHealth.mockRejectedValueOnce(new Error("Network unavailable"));
    render(<App />);

    expect(await screen.findByText("API offline")).toBeInTheDocument();
  });

  it("rejects a lookalike host before calling the save endpoint", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);

    const input = screen.getByRole("textbox", { name: /github repository url/i });
    await user.type(input, "https://github.com.evil.test/owner/repository");
    await user.click(screen.getByRole("button", { name: /save to workspace/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/secure github repository url/i);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(saveRepository).not.toHaveBeenCalled();
  });

  it("persists a public repository and displays its live directory listing", async () => {
    const user = userEvent.setup();
    getRepositoryBranches.mockResolvedValue({
      repository_id: repository.id,
      selected_branch: "main",
      default_branch: "main",
      items: [{ name: "main", commit_sha: "a".repeat(40), protected: true }],
      may_be_truncated: false,
    });
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    await user.type(
      screen.getByRole("textbox", { name: /github repository url/i }),
      "https://github.com/digvijay1129/RepoLens.git",
    );
    await user.click(screen.getByRole("button", { name: /save to workspace/i }));

    expect(await screen.findByText(/Saved digvijay1129\/RepoLens to your workspace/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Code explorer" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /backend directory/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /README\.md/i })).toHaveAttribute(
      "href",
      "https://github.com/digvijay1129/RepoLens/blob/main/README.md",
    );
    expect(saveRepository).toHaveBeenCalledWith("https://github.com/digvijay1129/RepoLens");
    expect(getRepositoryContents).toHaveBeenCalledWith("digvijay1129", "RepoLens", {
      path: "",
      ref: "main",
    });
    expect(getRepositoryBranches).toHaveBeenCalledWith(repository.id);
  });

  it("shows a safe error when GitHub cannot save a repository", async () => {
    saveRepository.mockRejectedValueOnce(new Error("Public GitHub repository or path was not found."));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    await user.type(
      screen.getByRole("textbox", { name: /github repository url/i }),
      "https://github.com/unknown/not-found",
    );
    await user.click(screen.getByRole("button", { name: /save to workspace/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not found/i);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("loads a subdirectory when its folder is selected", async () => {
    const user = userEvent.setup();
    getRepositoryContents.mockImplementation(async (_owner, _repository, options) => ({
      ...directory,
      path: options.path || "",
      items: options.path
        ? [{ name: "main.py", path: "backend/main.py", type: "file", sha: "file1", size: 30, html_url: "https://github.com/digvijay1129/RepoLens/blob/main/backend/main.py", download_url: null }]
        : directory.items,
    }));
    render(<App />);

    await screen.findByText("Recent repositories");
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    await user.type(screen.getByRole("textbox", { name: /github repository url/i }), "https://github.com/digvijay1129/RepoLens");
    await user.click(screen.getByRole("button", { name: /save to workspace/i }));
    await screen.findByRole("link", { name: /README\.md/i });
    await user.click(screen.getByRole("button", { name: /backend directory/i }));

    expect(await screen.findByRole("link", { name: /main\.py/i })).toHaveAttribute(
      "href",
      "https://github.com/digvijay1129/RepoLens/blob/main/backend/main.py",
    );
    await waitFor(() => expect(getRepositoryContents).toHaveBeenLastCalledWith(
      "digvijay1129",
      "RepoLens",
      { path: "backend", ref: "main" },
    ));
  });

  it("changes the selected branch persistently", async () => {
    const user = userEvent.setup();
    getSavedRepositories.mockResolvedValueOnce([repository]);
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /^code explorer/i }));
    await screen.findByRole("heading", { name: "Code explorer" });
    await screen.findByRole("option", { name: "feature/add-tests" });

    await user.selectOptions(screen.getByRole("combobox", { name: /select branch/i }), "feature/add-tests");
    await waitFor(() => expect(selectRepositoryBranch).toHaveBeenCalledWith(repository.id, "feature/add-tests"));
    await waitFor(() => expect(screen.getByRole("combobox", { name: /select branch/i }).value).toBe("feature/add-tests"));
  });

  it("removes a repository from the authenticated workspace", async () => {
    const user = userEvent.setup();
    getSavedRepositories.mockResolvedValueOnce([repository]);
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /^repositories/i }));
    await screen.findByRole("heading", { name: /your repositories/i });

    await user.click(screen.getByRole("button", { name: /remove digvijay1129\/repolens/i }));

    expect(deleteSavedRepository).toHaveBeenCalledWith(repository.id);
    expect(await screen.findByText(/removed from your workspace/i)).toBeInTheDocument();
  });

  it("closes the connect modal with Escape", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("clears the session and returns to the sign-in screen on sign out", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /sign out/i }));

    expect(clearAccessToken).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: /sign in to repolens/i })).toBeInTheDocument();
  });

  it("opens AI chat with a suggested question for a connected repository", async () => {
    const user = userEvent.setup();
    const indexedRepository = { ...repository, indexing_status: "indexed", embedding_status: "embedded" };
    getSavedRepositories.mockResolvedValueOnce([indexedRepository]);
    render(<App />);

    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /where is authentication handled/i }));

    expect(await screen.findByRole("heading", { name: /ask your codebase/i })).toBeInTheDocument();
    expect(await screen.findByRole("textbox", { name: "Ask about this repository" })).toHaveValue("Where is authentication handled?");
  });




  it("asks a repository question and renders a grounded answer with citations", async () => {
    const user = userEvent.setup();
    const indexedRepository = {
      ...repository,
      indexing_status: "indexed",
      indexed_commit_sha: "a".repeat(40),
    };
    getSavedRepositories.mockResolvedValueOnce([indexedRepository]);
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /^code explorer/i }));
    await screen.findByRole("heading", { name: "Code explorer" });
    expect(screen.getByRole("heading", { name: "Ask RepoLens" })).toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "Ask about this repository" }),
      "How is authentication validated?",
    );
    await user.click(screen.getByRole("button", { name: /ask question/i }));

    expect(chatWithSavedRepository).toHaveBeenCalledWith(indexedRepository.id, {
      message: "How is authentication validated?",
    });
    expect(await screen.findByText("Token validation is delegated to authenticate_user [S1].")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /backend\/app\/auth\.py/ })).toHaveAttribute("href", expect.stringContaining("#L12-L28"));

    const priorClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    try {
      await user.click(screen.getByRole("button", { name: /copy repolens answer message-assistant-1/i }));
      expect(writeText).toHaveBeenCalledWith("Token validation is delegated to authenticate_user [S1].");
      expect(await screen.findByText("Copied")).toBeInTheDocument();
    } finally {
      if (priorClipboard) Object.defineProperty(navigator, "clipboard", priorClipboard);
      else delete navigator.clipboard;
    }
  });

  it("searches an indexed repository and renders a line-level source citation", async () => {
    const user = userEvent.setup();
    const indexedRepository = { ...repository, indexing_status: "indexed", embedding_status: "pending" };
    getSavedRepositories.mockResolvedValueOnce([indexedRepository]);
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /^code explorer/i }));
    await screen.findByRole("heading", { name: "Code explorer" });
    expect(screen.getByRole("heading", { name: "Search this codebase" })).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Search repository source" }), "authenticate_user");
    await user.selectOptions(screen.getByRole("combobox", { name: "Retrieval mode" }), "keyword");
    await user.click(screen.getByRole("button", { name: /search sources/i }));

    expect(searchSavedRepository).toHaveBeenCalledWith(indexedRepository.id, {
      query: "authenticate_user", mode: "keyword", limit: 8,
    });
    expect(await screen.findByText("backend/app/auth.py")).toBeInTheDocument();
    expect(screen.getByText("Lines 12–28")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open cited lines/i })).toHaveAttribute("href", expect.stringContaining("#L12-L28"));
  });

  it("generates embeddings for an indexed repository and shows the active model", async () => {
    const user = userEvent.setup();
    const indexedRepository = {
      ...repository,
      indexing_status: "indexed",
      embedding_status: "pending",
      indexed_commit_sha: "a".repeat(40),
    };
    getSavedRepositories.mockResolvedValueOnce([indexedRepository]);
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /^code explorer/i }));
    await screen.findByRole("heading", { name: "Code explorer" });

    const embeddingButton = screen.getByRole("button", { name: /generate embeddings/i });
    expect(embeddingButton).toBeEnabled();
    await user.click(embeddingButton);

    expect(startRepositoryEmbeddings).toHaveBeenCalledWith(indexedRepository.id);
    expect(await screen.findByText("Generated 1 embeddings with openai_compatible/test-embedding-model.")).toBeInTheDocument();
    expect(screen.getAllByText(/test-embedding-model/).length).toBeGreaterThan(0);
  });

  it("starts source indexing and shows the completed chunk snapshot", async () => {
    const user = userEvent.setup();
    getSavedRepositories.mockResolvedValueOnce([repository]);
    render(<App />);
    await screen.findByText("Recent repositories");
    await user.click(screen.getByRole("button", { name: /^code explorer/i }));
    await screen.findByRole("heading", { name: "Code explorer" });

    expect(screen.getByRole("heading", { name: "Source & embedding pipeline" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /index source files/i }));

    expect(startRepositoryIndex).toHaveBeenCalledWith(repository.id);
    expect(await screen.findByText("Indexing completed successfully.")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText(/Commit/)).toBeInTheDocument();
  });

});
