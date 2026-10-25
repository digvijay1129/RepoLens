import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App.jsx";
import { getApiHealth } from "./lib/api.js";

vi.mock("./lib/api.js", () => ({
  getApiHealth: vi.fn(),
}));

describe("RepoLens dashboard", () => {
  beforeEach(() => {
    getApiHealth.mockResolvedValue({ status: "ok" });
  });

  it("renders the main dashboard and core product areas", async () => {
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

  it("rejects a lookalike host and announces the validation error", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);

    const input = screen.getByRole("textbox", { name: /github repository url/i });
    await user.type(input, "https://github.com.evil.test/owner/repository");
    await user.click(screen.getByRole("button", { name: /validate repository url/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/secure github repository url/i);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("validates a repository URL without claiming to connect or store it", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);

    await user.type(
      screen.getByRole("textbox", { name: /github repository url/i }),
      "https://github.com/digvijay1129/RepoLens.git",
    );
    await user.click(screen.getByRole("button", { name: /validate repository url/i }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByText(/URL format is valid for digvijay1129\/RepoLens/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing has been stored yet/i)).toBeInTheDocument();
  });

  it("closes the repository modal with Escape", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getAllByRole("button", { name: /connect repository/i })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("keeps suggested questions explicitly in preview mode during Phase 1B", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /where is authentication handled/i }));

    expect(await screen.findByText(/Question suggestion preview/i)).toBeInTheDocument();
    expect(screen.getByText(/repository retrieval and AI chat will be connected in Phase 6/i)).toBeInTheDocument();
    expect(getApiHealth).toHaveBeenCalled();
  });
});
