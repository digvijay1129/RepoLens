import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App.jsx";
import { getApiHealth, getRepositoryContents, inspectRepository } from "./lib/api.js";

vi.mock("./lib/api.js", () => ({
  getApiHealth: vi.fn(),
  getRepositoryContents: vi.fn(),
  inspectRepository: vi.fn(),
}));

const repository = {
  id: 123,
  name: "RepoLens",
  full_name: "digvijay1129/RepoLens",
  description: "GitHub codebase intelligence",
  html_url: "https://github.com/digvijay1129/RepoLens",
  default_branch: "main",
  language: "Python",
  stargazers_count: 2,
  forks_count: 1,
  open_issues_count: 1,
  size: 200,
  updated_at: "2026-10-25T00:00:00Z",
  license_name: "MIT License",
  archived: false,
  private: false,
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

describe("RepoLens dashboard and public repository browsing", () => {
  beforeEach(() => {
    getApiHealth.mockResolvedValue({ status: "ok" });
    inspectRepository.mockResolvedValue(repository);
    getRepositoryContents.mockResolvedValue(directory);
  });

  it("renders the dashboard and API status", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /understand the code/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /connect repository/i })).toBeInTheDocument();
    expect(screen.getByText("Recent repositories")).toBeInTheDocument();
    expect(await screen.findByText("API online")).toBeInTheDocument();
  });

  it("shows an offline state when the backend health request fails", async () => {
    getApiHealth.mockRejectedValueOnce(new Error("Network unavailable"));
    render(<App />);

    expect(await screen.findByText("API offline")).toBeInTheDocument();
  });

  it("rejects a lookalike host before making a repository API request", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);

    const input = screen.getByRole("textbox", { name: /github repository url/i });
    await user.type(input, "https://github.com.evil.test/owner/repository");
    await user.click(screen.getByRole("button", { name: /inspect public repository/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/secure github repository url/i);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(inspectRepository).not.toHaveBeenCalled();
  });

  it("connects to a public repository and displays the live directory listing", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    await user.type(
      screen.getByRole("textbox", { name: /github repository url/i }),
      "https://github.com/digvijay1129/RepoLens.git",
    );
    await user.click(screen.getByRole("button", { name: /inspect public repository/i }));

    expect(await screen.findByText(/Connected to digvijay1129\/RepoLens/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Code explorer" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /backend directory/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /README\.md/i })).toHaveAttribute(
      "href",
      "https://github.com/digvijay1129/RepoLens/blob/main/README.md",
    );
    expect(inspectRepository).toHaveBeenCalledWith("https://github.com/digvijay1129/RepoLens");
    expect(getRepositoryContents).toHaveBeenCalledWith("digvijay1129", "RepoLens", {
      path: "",
      ref: "main",
    });
  });

  it("shows a safe error when GitHub cannot inspect a repository", async () => {
    inspectRepository.mockRejectedValueOnce(new Error("Public GitHub repository or path was not found."));
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    await user.type(
      screen.getByRole("textbox", { name: /github repository url/i }),
      "https://github.com/unknown/not-found",
    );
    await user.click(screen.getByRole("button", { name: /inspect public repository/i }));

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

    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    await user.type(screen.getByRole("textbox", { name: /github repository url/i }), "https://github.com/digvijay1129/RepoLens");
    await user.click(screen.getByRole("button", { name: /inspect public repository/i }));
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

  it("closes the connect modal with Escape", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("keeps suggested code questions in preview mode until the RAG phase", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /where is authentication handled/i }));

    expect(await screen.findByText(/Question suggestion preview/i)).toBeInTheDocument();
    expect(screen.getByText(/repository retrieval and AI chat will be connected in Phase 6/i)).toBeInTheDocument();
  });
});
