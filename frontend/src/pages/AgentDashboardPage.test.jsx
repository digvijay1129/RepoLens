import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AgentDashboardPage from "./AgentDashboardPage.jsx";

import {
  approveAgentAction,
  createAgentTask,
  createRepositoryMemory,
  denyAgentAction,
  getAgentApprovals,
  getAgentDelegations,
  getAgentTasks,
  getAgentTeam,
  getAgentTask,
  getAgentToolExecutions,
  getRepositoryMemories,
} from "../lib/api.js";

vi.mock("../lib/api.js", () => ({
  approveAgentAction: vi.fn(),
  cancelAgentTask: vi.fn(),
  createAgentTask: vi.fn(),
  createRepositoryMemory: vi.fn(),
  deleteRepositoryMemory: vi.fn(),
  denyAgentAction: vi.fn(),
  getAgentApprovals: vi.fn(),
  getAgentDelegations: vi.fn(),
  getAgentTasks: vi.fn(),
  getAgentTeam: vi.fn(),
  getAgentTask: vi.fn(),
  getAgentToolExecutions: vi.fn(),
  getRepositoryMemories: vi.fn(),
  resumeAgentTask: vi.fn(),
  runAgentTask: vi.fn(),
  updateRepositoryMemory: vi.fn(),
}));

const repository = {
  id: "repo-1",
  full_name: "acme/payments",
  indexing_status: "indexed",
  indexed_commit_sha: "a".repeat(40),
};

const task = {
  id: "task-12345678",
  repository_id: repository.id,
  goal: "Review authentication and token validation",
  status: "awaiting_approval",
  approval_mode: "approve_each",
  max_steps: 4,
  total_tool_calls: 1,
  steps: [
    {
      id: "step-1",
      step_key: "review_auth",
      title: "Review authentication module",
      description: "Inspect authentication handlers and token validation.",
      depends_on: [],
      status: "pending",
    },
  ],
  updated_at: "2026-11-22T10:00:00Z",
  latest_error: "A proposed read-only tool action is waiting for owner approval.",
};

const approval = {
  id: "approval-12345678",
  task_id: task.id,
  step_id: "step-1",
  status: "pending",
  tool_name: "repository_overview",
  tool_arguments: {},
  action_hash: "f".repeat(64),
  specialist_key: "research",
  policy_reason: "This task requires owner approval for every proposed tool call.",
  expires_at: "2026-11-22T10:15:00Z",
  requested_at: "2026-11-22T10:00:00Z",
  decision_comment: null,
};

function renderDashboard() {
  return render(
    <AgentDashboardPage
      repositories={[repository]}
      selectedRepositoryKey={repository.full_name}
      onSelectRepository={vi.fn()}
    />,
  );
}

describe("Agent dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAgentTasks.mockResolvedValue([]);
    getRepositoryMemories.mockResolvedValue([]);
    getAgentTask.mockResolvedValue(task);
    getAgentTeam.mockResolvedValue({
      coordinator: { name: "Main Coordinator Agent" },
      specialists: [],
      step_assignments: [],
    });
    getAgentDelegations.mockResolvedValue([]);
    getAgentApprovals.mockResolvedValue([]);
    getAgentToolExecutions.mockResolvedValue([]);
    createAgentTask.mockResolvedValue({ ...task, status: "planned" });
    createRepositoryMemory.mockResolvedValue({ id: "memory-1" });
    approveAgentAction.mockResolvedValue({ ...approval, status: "approved" });
    denyAgentAction.mockResolvedValue({ ...approval, status: "denied" });
  });

  it("creates an approval-controlled repository task", async () => {
    const user = userEvent.setup();
    renderDashboard();

    await screen.findByRole("heading", { name: "Agent dashboard" });
    await user.type(
      screen.getByRole("textbox", { name: "New task goal" }),
      "Review authentication and token validation",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Execution control" }),
      "approve_each",
    );
    await user.click(screen.getByRole("button", { name: /create & plan task/i }));

    await waitFor(() => expect(createAgentTask).toHaveBeenCalledWith({
      repository_id: repository.id,
      goal: "Review authentication and token validation",
      approval_mode: "approve_each",
      max_steps: 8,
    }));
    expect(await screen.findByText(/Task planned successfully/)).toBeInTheDocument();
  });

  it("shows exact pending tool arguments and records an owner approval", async () => {
    const user = userEvent.setup();
    getAgentTasks.mockResolvedValue([task]);
    getAgentApprovals.mockResolvedValue([approval]);
    renderDashboard();

    await screen.findByRole("heading", { name: task.goal });
    await user.click(screen.getByRole("button", { name: /approvals/i }));

    expect(await screen.findByText("repository_overview")).toBeInTheDocument();
    expect(screen.getByText(/exact proposed arguments/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /approve action/i }));

    await waitFor(() => expect(approveAgentAction).toHaveBeenCalledWith(
      approval.id,
      "Approved from the RepoLens agent dashboard.",
    ));
    expect(await screen.findByText(/resume the task to execute this exact proposed tool call/i)).toBeInTheDocument();
  });

  it("records an explicit denial through the approval center", async () => {
    const user = userEvent.setup();
    getAgentTasks.mockResolvedValue([task]);
    getAgentApprovals.mockResolvedValue([approval]);
    renderDashboard();

    await screen.findByRole("heading", { name: task.goal });
    await user.click(screen.getByRole("button", { name: /approvals/i }));
    await user.click(await screen.findByRole("button", { name: /deny action/i }));

    await waitFor(() => expect(denyAgentAction).toHaveBeenCalledWith(
      approval.id,
      "Denied from the RepoLens agent dashboard.",
    ));
  });

  it("saves user-curated repository memory", async () => {
    const user = userEvent.setup();
    getAgentTasks.mockResolvedValue([task]);
    renderDashboard();
    await screen.findByRole("heading", { name: "Agent dashboard" });
    await user.click(screen.getByRole("button", { name: /memory/i }));

    await user.type(screen.getByRole("textbox", { name: "Title" }), "Authentication convention");
    await user.type(
      screen.getByRole("textbox", { name: "Knowledge" }),
      "All protected endpoints use the shared JWT dependency.",
    );
    await user.click(screen.getByRole("button", { name: /save memory/i }));

    await waitFor(() => expect(createRepositoryMemory).toHaveBeenCalledWith(repository.id, {
      memory_type: "note",
      title: "Authentication convention",
      content: "All protected endpoints use the shared JWT dependency.",
      tags: [],
      importance: 3,
      confidence: 1,
    }));
  });
});
