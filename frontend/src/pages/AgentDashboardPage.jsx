import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Bot,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Clock3,
  Code2,
  FileText,
  Fingerprint,
  History,
  LoaderCircle,
  LockKeyhole,
  MemoryStick,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldX,
  Sparkles,
  Users,
  X,
  XCircle,
} from "lucide-react";
import {
  approveAgentAction,
  cancelAgentTask,
  createAgentTask,
  createRepositoryMemory,
  deleteRepositoryMemory,
  denyAgentAction,
  getAgentApprovals,
  getAgentDelegations,
  getAgentTasks,
  getAgentTeam,
  getAgentTask,
  getAgentToolExecutions,
  getRepositoryMemories,
  resumeAgentTask,
  runAgentTask,
  updateRepositoryMemory,
} from "../lib/api.js";

const tabs = [
  { id: "execution", label: "Execution", icon: Activity },
  { id: "team", label: "Agent team", icon: Users },
  { id: "approvals", label: "Approvals", icon: ShieldCheck },
  { id: "memory", label: "Memory", icon: BrainCircuit },
  { id: "history", label: "Tool history", icon: History },
];

const statusTone = {
  completed: "success",
  succeeded: "success",
  executed: "success",
  approved: "success",
  running: "info",
  planned: "info",
  awaiting_approval: "warning",
  pending: "warning",
  paused: "warning",
  failed: "danger",
  denied: "danger",
  expired: "danger",
  cancelled: "muted",
  assigned: "muted",
};

function StatusPill({ value }) {
  const tone = statusTone[value] || "muted";
  return <span className={"agent-status agent-status--" + tone}><i />{String(value || "unknown").replaceAll("_", " ")}</span>;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function shortId(value) {
  return value ? String(value).slice(0, 8) : "—";
}

function EmptyState({ icon: Icon = CircleDashed, title, description }) {
  return (
    <div className="agent-empty-state">
      <span><Icon size={21} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function SectionHeading({ kicker, title, description, action }) {
  return (
    <div className="agent-section-heading">
      <div>
        {kicker && <span className="eyebrow"><span className="eyebrow-line" />{kicker}</span>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}

export default function AgentDashboardPage({ repositories = [], selectedRepositoryKey, onSelectRepository }) {
  const [repositoryId, setRepositoryId] = useState("");
  const [tasks, setTasks] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [task, setTask] = useState(null);
  const [team, setTeam] = useState(null);
  const [delegations, setDelegations] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [memories, setMemories] = useState([]);
  const [activeTab, setActiveTab] = useState("execution");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [goal, setGoal] = useState("");
  const [approvalMode, setApprovalMode] = useState("approve_each");
  const [maxSteps, setMaxSteps] = useState("8");
  const [memoryQuery, setMemoryQuery] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [memoryTitle, setMemoryTitle] = useState("");
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryType, setMemoryType] = useState("note");

  const preferredRepository = repositories.find((item) => item.full_name === selectedRepositoryKey);
  const activeRepository = repositories.find((item) => item.id === repositoryId) || null;
  const indexedRepositories = repositories.filter(
    (item) => item.indexing_status === "indexed" && item.indexed_commit_sha,
  );
  const pendingApprovals = approvals.filter((item) => item.status === "pending");
  const completedSteps = task?.steps?.filter((step) => step.status === "succeeded").length || 0;
  const totalSteps = task?.steps?.length || 0;
  const progress = totalSteps ? Math.round((completedSteps / totalSteps) * 100) : 0;

  useEffect(() => {
    const next = (
      preferredRepository?.indexing_status === "indexed" && preferredRepository?.indexed_commit_sha
        ? preferredRepository.id
        : indexedRepositories[0]?.id || repositories[0]?.id || ""
    );
    setRepositoryId(next);
  }, [preferredRepository?.id, indexedRepositories.map((item) => item.id).join("|"), repositories.map((item) => item.id).join("|")]);

  const loadTasks = useCallback(async (nextRepositoryId = repositoryId) => {
    if (!nextRepositoryId) {
      setTasks([]);
      setSelectedTaskId("");
      setTask(null);
      return;
    }
    const result = await getAgentTasks(nextRepositoryId, 50);
    const items = Array.isArray(result) ? result : result?.items || [];
    setTasks(items);
    setSelectedTaskId((current) => (
      items.some((item) => item.id === current) ? current : (items[0]?.id || "")
    ));
  }, [repositoryId]);

  const loadMemories = useCallback(async (nextRepositoryId = repositoryId) => {
    if (!nextRepositoryId) {
      setMemories([]);
      return;
    }
    const items = await getRepositoryMemories(nextRepositoryId, {
      query: memoryQuery,
      includeInactive,
      limit: 100,
    });
    setMemories(Array.isArray(items) ? items : items?.items || []);
  }, [repositoryId, memoryQuery, includeInactive]);

  const refreshWorkspace = useCallback(async () => {
    if (!repositoryId) return;
    setError("");
    setLoading(true);
    try {
      await Promise.all([loadTasks(repositoryId), loadMemories(repositoryId)]);
    } catch (requestError) {
      setError(requestError?.message || "Unable to load agent workspace.");
    } finally {
      setLoading(false);
    }
  }, [repositoryId, loadTasks, loadMemories]);

  useEffect(() => {
    let mounted = true;
    if (!repositoryId) {
      setLoading(false);
      setTasks([]);
      setMemories([]);
      setSelectedTaskId("");
      return undefined;
    }
    setLoading(true);
    setError("");
    Promise.all([
      getAgentTasks(repositoryId, 50),
      getRepositoryMemories(repositoryId, { limit: 100 }),
    ]).then(([taskResult, memoryResult]) => {
      if (!mounted) return;
      const taskItems = Array.isArray(taskResult) ? taskResult : taskResult?.items || [];
      const memoryItems = Array.isArray(memoryResult) ? memoryResult : memoryResult?.items || [];
      setTasks(taskItems);
      setMemories(memoryItems);
      setSelectedTaskId((current) => taskItems.some((item) => item.id === current) ? current : (taskItems[0]?.id || ""));
    }).catch((requestError) => {
      if (mounted) setError(requestError?.message || "Unable to load agent workspace.");
    }).finally(() => {
      if (mounted) setLoading(false);
    });
    return () => { mounted = false; };
  }, [repositoryId]);

  const loadTaskDetail = useCallback(async (taskId = selectedTaskId) => {
    if (!taskId) {
      setTask(null);
      setTeam(null);
      setDelegations([]);
      setApprovals([]);
      setExecutions([]);
      return;
    }
    setDetailLoading(true);
    try {
      const results = await Promise.allSettled([
        getAgentTask(taskId),
        getAgentTeam(taskId),
        getAgentDelegations(taskId),
        getAgentApprovals(taskId),
        getAgentToolExecutions(taskId),
      ]);
      if (results[0].status === "rejected") throw results[0].reason;
      setTask(results[0].value);
      setTeam(results[1].status === "fulfilled" ? results[1].value : null);
      setDelegations(results[2].status === "fulfilled" ? results[2].value : []);
      setApprovals(results[3].status === "fulfilled" ? results[3].value : []);
      setExecutions(results[4].status === "fulfilled" ? results[4].value : []);
    } catch (requestError) {
      setError(requestError?.message || "Unable to load task details.");
    } finally {
      setDetailLoading(false);
    }
  }, [selectedTaskId]);

  useEffect(() => {
    loadTaskDetail(selectedTaskId);
  }, [selectedTaskId, loadTaskDetail]);

  useEffect(() => {
    if (!repositoryId) return undefined;
    const refresh = () => {
      getAgentTasks(repositoryId, 50)
        .then((result) => setTasks(Array.isArray(result) ? result : result?.items || []))
        .catch(() => {});
    };
    // The task API is refreshed on focus instead of running a permanent polling loop.
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [repositoryId]);

  async function handleCreateTask(event) {
    event.preventDefault();
    if (!repositoryId || !goal.trim()) return;
    setBusy("create");
    setError("");
    setNotice("");
    try {
      const created = await createAgentTask({
        repository_id: repositoryId,
        goal: goal.trim(),
        approval_mode: approvalMode,
        max_steps: Number(maxSteps),
      });
      setGoal("");
      setSelectedTaskId(created.id);
      setTask(created);
      setNotice("Task planned successfully. Review the plan before starting execution.");
      const result = await getAgentTasks(repositoryId, 50);
      setTasks(Array.isArray(result) ? result : result?.items || []);
    } catch (requestError) {
      setError(requestError?.message || "Unable to create the agent task.");
    } finally {
      setBusy("");
    }
  }

  async function performTaskAction(action, label) {
    if (!task?.id) return;
    setBusy(label);
    setError("");
    setNotice("");
    try {
      const result = await action(task.id);
      if (result?.id) setTask(result);
      await Promise.all([loadTaskDetail(task.id), loadTasks(repositoryId)]);
      if (result?.status === "awaiting_approval") {
        setActiveTab("approvals");
        setNotice("The agent paused safely. Review the proposed action before continuing.");
      } else if (result?.status === "completed") {
        setActiveTab("execution");
        setNotice("Agent task completed successfully.");
      } else if (result?.status === "cancelled") {
        setNotice("Agent task cancelled.");
      } else {
        setNotice("Task state updated.");
      }
    } catch (requestError) {
      setError(requestError?.message || "The task action could not be completed.");
      await loadTaskDetail(task.id);
    } finally {
      setBusy("");
    }
  }

  async function handleDecision(approval, decision) {
    setBusy(decision + approval.id);
    setError("");
    setNotice("");
    try {
      if (decision === "approve") {
        await approveAgentAction(approval.id, "Approved from the RepoLens agent dashboard.");
        setNotice("Action approved. Resume the task to execute this exact proposed tool call.");
      } else {
        await denyAgentAction(approval.id, "Denied from the RepoLens agent dashboard.");
        setNotice("Action denied. The task has been stopped.");
      }
      await loadTaskDetail(task?.id);
      await loadTasks(repositoryId);
    } catch (requestError) {
      setError(requestError?.message || "Unable to record the approval decision.");
    } finally {
      setBusy("");
    }
  }

  async function handleCreateMemory(event) {
    event.preventDefault();
    if (!repositoryId || !memoryTitle.trim() || !memoryContent.trim()) return;
    setBusy("memory-create");
    setError("");
    try {
      await createRepositoryMemory(repositoryId, {
        memory_type: memoryType,
        title: memoryTitle.trim(),
        content: memoryContent.trim(),
        tags: [],
        importance: 3,
        confidence: 1,
      });
      setMemoryTitle("");
      setMemoryContent("");
      await loadMemories(repositoryId);
      setNotice("Repository memory saved.");
    } catch (requestError) {
      setError(requestError?.message || "Unable to save repository memory.");
    } finally {
      setBusy("");
    }
  }

  async function handleMemoryArchive(memory, restore = false) {
    setBusy("memory-" + memory.id);
    setError("");
    try {
      await updateRepositoryMemory(memory.id, { is_active: restore });
      await loadMemories(repositoryId);
      setNotice(restore ? "Memory restored." : "Memory archived.");
    } catch (requestError) {
      setError(requestError?.message || "Unable to update repository memory.");
    } finally {
      setBusy("");
    }
  }

  async function handleMemoryDelete(memory) {
    if (!window.confirm("Permanently delete this repository memory?")) return;
    setBusy("memory-" + memory.id);
    setError("");
    try {
      await deleteRepositoryMemory(memory.id);
      await loadMemories(repositoryId);
      setNotice("Memory permanently deleted.");
    } catch (requestError) {
      setError(requestError?.message || "Unable to delete repository memory.");
    } finally {
      setBusy("");
    }
  }

  const selectedApproval = useMemo(
    () => pendingApprovals.find((item) => item.status === "pending"),
    [pendingApprovals],
  );
  const canResume = task && ["planned", "paused", "awaiting_approval", "running"].includes(task.status);
  const canRun = task && ["planned", "paused"].includes(task.status);
  const canCancel = task && !["completed", "failed", "cancelled"].includes(task.status);

  if (!indexedRepositories.length) {
    return (
      <section className="agent-page animate-fade-in">
        <header className="agent-page-heading">
          <span className="eyebrow"><span className="eyebrow-line" /> AUTONOMOUS WORKSPACE</span>
          <h1>Agent dashboard</h1>
          <p>Plan repository work, coordinate specialist agents, and control every proposed action.</p>
        </header>
        <div className="agent-empty-repository panel">
          <span className="agent-hero-icon"><BrainCircuit size={26} /></span>
          <h2>Prepare a repository for autonomous analysis</h2>
          <p>Connect a repository and finish source indexing before creating an agent task. RepoLens pins each task to an indexed commit.</p>
          {repositories.length > 0 ? (
            <div className="agent-repository-picker">
              <label htmlFor="agent-repository-select">Choose repository</label>
              <select id="agent-repository-select" value={repositoryId} onChange={(event) => {
                setRepositoryId(event.target.value);
                const selected = repositories.find((item) => item.id === event.target.value);
                if (selected) onSelectRepository?.(selected.full_name);
              }}>
                {repositories.map((item) => <option key={item.id} value={item.id}>{item.full_name} · {item.indexing_status}</option>)}
              </select>
            </div>
          ) : <p className="agent-empty-caption">No saved repositories are connected to this workspace yet.</p>}
          <div className="agent-prerequisite-row">
            <span><CheckCircle2 size={15} /> Connect GitHub repository</span>
            <span><CircleDashed size={15} /> Index source files</span>
          </div>
          <button className="button button-secondary" type="button" onClick={() => window.location.assign("/repositories")}>Open repositories <ArrowRight size={15} /></button>
        </div>
      </section>
    );
  }

  return (
    <section className="agent-page animate-fade-in">
      <header className="agent-page-heading">
        <div>
          <span className="eyebrow"><span className="eyebrow-line" /> AUTONOMOUS WORKSPACE</span>
          <h1>Agent dashboard</h1>
          <p>Plan repository work, coordinate specialist agents, and keep humans in control.</p>
        </div>
        <div className="agent-header-actions">
          <label className="agent-repository-select">
            <span>Repository</span>
            <select value={repositoryId} onChange={(event) => {
              setRepositoryId(event.target.value);
              const selected = repositories.find((item) => item.id === event.target.value);
              if (selected) onSelectRepository?.(selected.full_name);
            }}>
              {indexedRepositories.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
            </select>
          </label>
          <button className="button button-secondary" type="button" onClick={refreshWorkspace} disabled={loading || !repositoryId}>
            <RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>
      </header>

      {error && <div className="agent-alert agent-alert--error" role="alert"><AlertCircle size={17} /><span>{error}</span><button type="button" aria-label="Dismiss error" onClick={() => setError("")}><X size={15} /></button></div>}
      {notice && <div className="agent-alert agent-alert--success" role="status"><CheckCircle2 size={17} /><span>{notice}</span><button type="button" aria-label="Dismiss notice" onClick={() => setNotice("")}><X size={15} /></button></div>}

      <div className="agent-metrics-grid">
        <article className="agent-metric panel"><span className="agent-metric-icon"><Bot size={18} /></span><div><span>Agent tasks</span><strong>{tasks.length}</strong></div></article>
        <article className="agent-metric panel"><span className="agent-metric-icon agent-metric-icon--warning"><ShieldCheck size={18} /></span><div><span>Pending approvals</span><strong>{tasks.filter((item) => item.status === "awaiting_approval").length}</strong></div></article>
        <article className="agent-metric panel"><span className="agent-metric-icon agent-metric-icon--success"><CheckCircle2 size={18} /></span><div><span>Completed tasks</span><strong>{tasks.filter((item) => item.status === "completed").length}</strong></div></article>
        <article className="agent-metric panel"><span className="agent-metric-icon agent-metric-icon--blue"><MemoryStick size={18} /></span><div><span>Repository memories</span><strong>{memories.length}</strong></div></article>
      </div>

      <div className="agent-main-grid">
        <aside className="agent-task-sidebar panel">
          <div className="agent-panel-heading">
            <div><h2>Tasks</h2><p>{tasks.length} in this repository</p></div>
            <span className="agent-count">{tasks.length}</span>
          </div>
          <form className="agent-create-form" onSubmit={handleCreateTask}>
            <label htmlFor="agent-goal">New task goal</label>
            <textarea id="agent-goal" rows="3" maxLength="4000" value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="Example: Review authentication, trace token validation, and summarize security risks." />
            <div className="agent-form-row">
              <label htmlFor="agent-approval-mode">Execution control</label>
              <select id="agent-approval-mode" value={approvalMode} onChange={(event) => setApprovalMode(event.target.value)}>
                <option value="approve_each">Approve every tool call</option>
                <option value="auto">Automatic read-only execution</option>
              </select>
            </div>
            <div className="agent-form-row">
              <label htmlFor="agent-max-steps">Maximum plan steps</label>
              <select id="agent-max-steps" value={maxSteps} onChange={(event) => setMaxSteps(event.target.value)}>
                {[4, 6, 8, 10, 12, 16, 20].map((value) => <option key={value} value={String(value)}>{value} steps</option>)}
              </select>
            </div>
            <button className="button button-primary button-full" type="submit" disabled={busy === "create" || !goal.trim()}>
              {busy === "create" ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}
              Create & plan task
            </button>
            <p className="agent-form-help"><LockKeyhole size={12} /> Tasks are pinned to the selected indexed commit.</p>
          </form>
          <div className="agent-task-list-heading"><span>RECENT TASKS</span><button type="button" onClick={() => loadTasks(repositoryId)} aria-label="Reload tasks"><RefreshCw size={13} /></button></div>
          <div className="agent-task-list">
            {loading ? <div className="agent-list-loading"><LoaderCircle size={17} className="spin" /> Loading tasks…</div> : tasks.length ? tasks.map((item) => (
              <button key={item.id} type="button" className={"agent-task-list-item" + (selectedTaskId === item.id ? " is-selected" : "")} onClick={() => setSelectedTaskId(item.id)}>
                <span className="agent-task-item-top"><span className="agent-task-item-id">#{shortId(item.id)}</span><StatusPill value={item.status} /></span>
                <strong>{item.goal}</strong>
                <span className="agent-task-item-bottom">{item.approval_mode === "approve_each" ? <ShieldCheck size={12} /> : <Sparkles size={12} />}{item.approval_mode === "approve_each" ? "Human approval" : "Automatic"}<span>·</span>{formatDate(item.updated_at)}</span>
              </button>
            )) : <div className="agent-task-list-empty">No tasks yet. Create your first repository task above.</div>}
          </div>
        </aside>

        <div className="agent-workspace-column">
          {!selectedTaskId ? (
            <div className="agent-task-welcome panel">
              <span className="agent-hero-icon"><BrainCircuit size={26} /></span>
              <h2>Your autonomous workspace</h2>
              <p>Create a task to let RepoLens plan repository research, delegate work to specialists, and return source-grounded findings.</p>
              <div className="agent-feature-chips"><span><Users size={14} /> Multi-agent</span><span><MemoryStick size={14} /> Persistent memory</span><span><ShieldCheck size={14} /> Human approval</span></div>
            </div>
          ) : detailLoading ? (
            <div className="agent-loading-panel panel"><LoaderCircle className="spin" size={20} /> Loading task workspace…</div>
          ) : task ? (
            <>
              <section className="agent-task-overview panel">
                <div className="agent-task-overview-top">
                  <div className="agent-task-heading-main">
                    <span className="agent-task-id">TASK #{shortId(task.id)} · {activeRepository?.full_name}</span>
                    <h2>{task.goal}</h2>
                    <div className="agent-task-meta"><StatusPill value={task.status} /><span>{task.approval_mode === "approve_each" ? <ShieldCheck size={13} /> : <Sparkles size={13} />}{task.approval_mode === "approve_each" ? "Owner approval required" : "Automatic mode"}</span><span><Clock3 size={13} /> Updated {formatDate(task.updated_at)}</span></div>
                  </div>
                  <div className="agent-task-actions">
                    {canRun && <button className="button button-primary button-small" type="button" disabled={!!busy} onClick={() => performTaskAction(runAgentTask, "run")}><Sparkles size={14} />{busy === "run" ? "Running…" : "Run task"}</button>}
                    {task.status === "awaiting_approval" && (
                      <button className="button button-primary button-small" type="button" disabled={!!busy || !!selectedApproval} title={selectedApproval ? "Decide the pending approval first" : "Resume approved work"} onClick={() => performTaskAction(resumeAgentTask, "resume")}><ArrowRight size={14} />{busy === "resume" ? "Resuming…" : "Resume task"}</button>
                    )}
                    {task.status === "paused" && <button className="button button-primary button-small" type="button" disabled={!!busy} onClick={() => performTaskAction(resumeAgentTask, "resume")}><ArrowRight size={14} />Resume</button>}
                    {canCancel && <button className="button button-quiet button-small" type="button" disabled={!!busy} onClick={() => performTaskAction(cancelAgentTask, "cancel")}><XCircle size={14} />Cancel</button>}
                  </div>
                </div>
                <div className="agent-progress-area">
                  <div className="agent-progress-label"><span>Plan progress</span><strong>{completedSteps} / {totalSteps} steps · {progress}%</strong></div>
                  <div className="agent-progress-track"><span style={{ width: progress + "%" }} /></div>
                  {task.status === "awaiting_approval" && <p className="agent-pending-note"><ShieldCheck size={14} /> Execution is paused until you decide the pending action.</p>}
                  {task.latest_error && <p className="agent-task-error">{task.latest_error}</p>}
                </div>
              </section>

              <nav className="agent-tabs" aria-label="Agent workspace sections">
                {tabs.map(({ id, label, icon: Icon }) => (
                  <button key={id} type="button" className={activeTab === id ? "is-active" : ""} onClick={() => setActiveTab(id)}>
                    <Icon size={15} />{label}
                    {id === "approvals" && pendingApprovals.length > 0 && <span className="agent-tab-count">{pendingApprovals.length}</span>}
                  </button>
                ))}
              </nav>

              {activeTab === "execution" && (
                <section className="agent-tab-content">
                  <SectionHeading kicker="EXECUTION PLAN" title="Task steps" description="Validated steps, dependencies and execution state." action={<span className="agent-inline-stat">{task.total_tool_calls || 0} tool calls</span>} />
                  {task.steps?.length ? <div className="agent-step-list">{task.steps.map((step, index) => (
                    <article className="agent-step-row panel" key={step.id || step.step_key}>
                      <span className={"agent-step-number " + (step.status === "succeeded" ? "is-done" : step.status === "failed" ? "is-failed" : "")}>{step.status === "succeeded" ? <Check size={15} /> : index + 1}</span>
                      <div className="agent-step-copy"><div className="agent-step-title"><strong>{step.title}</strong><StatusPill value={step.status} /></div><p>{step.description}</p><div className="agent-step-foot"><span>KEY: {step.step_key}</span>{step.depends_on?.length > 0 && <span>Depends on: {step.depends_on.join(", ")}</span>}<span>Specialist: {team?.step_assignments?.find((item) => item.step_key === step.step_key)?.specialist_name || "Assigned at execution"}</span></div></div>
                    </article>
                  ))}</div> : <EmptyState icon={FileText} title="No plan steps available" description="The planner has not returned any steps for this task." />}
                  {task.final_result && <div className="agent-result-card panel"><div className="agent-panel-heading"><div><h3><CheckCircle2 size={17} /> Final task report</h3><p>Coordinator's consolidated findings</p></div><StatusPill value={task.status} /></div><pre>{JSON.stringify(task.final_result, null, 2)}</pre></div>}
                </section>
              )}

              {activeTab === "team" && (
                <section className="agent-tab-content">
                  <SectionHeading kicker="MULTI-AGENT COORDINATION" title="Specialist team" description="Fixed specialist roles assigned by the coordinator to validated plan steps." />
                  <div className="agent-coordinator-card panel"><span className="agent-role-icon"><BrainCircuit size={19} /></span><div><strong>{team?.coordinator?.name || "Main Coordinator Agent"}</strong><p>{team?.coordinator?.mission || "Delegates plan steps and consolidates findings."}</p></div><StatusPill value={task.status} /></div>
                  <div className="agent-specialist-grid">{(team?.specialists || []).map((specialist) => (
                    <article className="agent-specialist-card panel" key={specialist.key}>
                      <div className="agent-specialist-top"><span className="agent-role-icon"><Bot size={17} /></span><StatusPill value={specialist.failed_delegations ? "failed" : specialist.completed_delegations ? "succeeded" : "assigned"} /></div>
                      <strong>{specialist.name}</strong><p>{specialist.mission}</p>
                      <div className="agent-specialist-stats"><span>{specialist.assigned_steps || 0} assigned steps</span><span>{specialist.completed_delegations || 0} completed</span></div>
                    </article>
                  ))}</div>
                  <SectionHeading title="Step assignments" description="The specialist selected for each persisted plan step." />
                  <div className="agent-table-wrap panel"><table className="agent-table"><thead><tr><th>Plan step</th><th>Specialist</th><th>State</th><th>Attempts</th></tr></thead><tbody>{(team?.step_assignments || []).map((item) => <tr key={item.step_key}><td><strong>{item.step_title}</strong><small>{item.step_key}</small></td><td>{item.specialist_name}</td><td><StatusPill value={item.step_status} /></td><td>{item.delegation_count}</td></tr>)}</tbody></table></div>
                  {!team && <EmptyState icon={Users} title="Team details unavailable" description="Refresh this task to load its coordinator and specialist assignments." />}
                </section>
              )}

              {activeTab === "approvals" && (
                <section className="agent-tab-content">
                  <SectionHeading kicker="HUMAN-IN-THE-LOOP" title="Approval center" description="Review exact proposed tool actions. An action is not executed until you approve it." />
                  {approvals.length ? <div className="agent-approval-list">{approvals.map((approval) => (
                    <article className={"agent-approval-card panel " + (approval.status === "pending" ? "is-pending" : "")} key={approval.id}>
                      <div className="agent-approval-top"><div><span className="agent-task-id">REQUEST #{shortId(approval.id)}</span><h3>{approval.tool_name}</h3></div><StatusPill value={approval.status} /></div>
                      <p className="agent-approval-reason">{approval.policy_reason}</p>
                      <div className="agent-approval-details"><span><Bot size={13} /> {approval.specialist_key.replaceAll("_", " ")}</span><span><Clock3 size={13} /> Expires {formatDate(approval.expires_at)}</span><span><Fingerprint size={13} /> SHA-256 {String(approval.action_hash || "").slice(0, 16)}…</span></div>
                      <div className="agent-code-block"><div>EXACT PROPOSED ARGUMENTS</div><pre>{JSON.stringify(approval.tool_arguments || {}, null, 2)}</pre></div>
                      {approval.decision_comment && <p className="agent-decision-comment">Decision: {approval.decision_comment}</p>}
                      {approval.status === "pending" && (
                        <div className="agent-approval-actions">
                          <button className="button button-primary button-small" type="button" disabled={!!busy} onClick={() => handleDecision(approval, "approve")}><Check size={14} />{busy === "approve" + approval.id ? "Approving…" : "Approve action"}</button>
                          <button className="button button-danger button-small" type="button" disabled={!!busy} onClick={() => handleDecision(approval, "deny")}><ShieldX size={14} />{busy === "deny" + approval.id ? "Denying…" : "Deny action"}</button>
                        </div>
                      )}
                      {approval.status === "approved" && <p className="agent-pending-note"><CheckCircle2 size={14} /> Approved. Resume the task to execute this stored action once.</p>}
                    </article>
                  ))}</div> : <EmptyState icon={ShieldCheck} title="No approval requests" description="When an approve-each task proposes a tool action, its exact arguments will appear here for your decision." />}
                </section>
              )}

              {activeTab === "memory" && (
                <section className="agent-tab-content">
                  <SectionHeading kicker="PERSISTENT CONTEXT" title="Repository memory" description="Curate architecture notes, conventions, decisions and troubleshooting knowledge." />
                  <form className="agent-memory-form panel" onSubmit={handleCreateMemory}>
                    <div className="agent-memory-form-heading"><span className="agent-role-icon"><MemoryStick size={18} /></span><div><strong>Add repository knowledge</strong><p>Saved memories are scoped to {activeRepository?.full_name}.</p></div></div>
                    <div className="agent-memory-form-grid"><label>Memory type<select value={memoryType} onChange={(event) => setMemoryType(event.target.value)}><option value="note">Note</option><option value="architecture">Architecture</option><option value="convention">Convention</option><option value="decision">Decision</option><option value="troubleshooting">Troubleshooting</option></select></label><label>Title<input value={memoryTitle} onChange={(event) => setMemoryTitle(event.target.value)} minLength={3} maxLength={160} placeholder="e.g. API authentication convention" required /></label></div>
                    <label className="agent-memory-content-label">Knowledge<textarea rows="3" value={memoryContent} onChange={(event) => setMemoryContent(event.target.value)} minLength={8} maxLength={6000} placeholder="Describe the repository knowledge the agent should remember…" required /></label>
                    <div className="agent-memory-form-actions"><span>Up to 6,000 characters · User-curated</span><button className="button button-primary button-small" type="submit" disabled={busy === "memory-create" || !memoryTitle.trim() || !memoryContent.trim()}><Plus size={14} />Save memory</button></div>
                  </form>
                  <div className="agent-memory-toolbar"><label className="agent-search-field"><Search size={15} /><input value={memoryQuery} onChange={(event) => setMemoryQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadMemories(repositoryId)} placeholder="Search repository memories…" /></label><label className="agent-checkbox"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />Include archived and expired</label><button className="button button-secondary button-small" type="button" onClick={() => loadMemories(repositoryId)}><Search size={13} />Search</button></div>
                  {memories.length ? <div className="agent-memory-list">{memories.map((memory) => (
                    <article className={"agent-memory-card panel " + (!memory.is_active ? "is-archived" : "")} key={memory.id}>
                      <div className="agent-memory-card-top"><span className="agent-memory-type">{memory.memory_type}</span><StatusPill value={memory.is_active ? (memory.expires_at && new Date(memory.expires_at) < new Date() ? "expired" : "succeeded") : "cancelled"} /></div>
                      <h3>{memory.title}</h3><p>{memory.content}</p>
                      <div className="agent-memory-meta"><span>Importance {memory.importance}/5</span><span>{memory.access_count} retrievals</span><span>Updated {formatDate(memory.updated_at)}</span></div>
                      <div className="agent-memory-actions">{memory.is_active ? <button type="button" className="button button-secondary button-small" disabled={!!busy} onClick={() => handleMemoryArchive(memory, false)}>Archive</button> : <button type="button" className="button button-secondary button-small" disabled={!!busy} onClick={() => handleMemoryArchive(memory, true)}>Restore</button>}<button type="button" className="button button-quiet button-small" disabled={!!busy} onClick={() => handleMemoryDelete(memory)}>Delete</button></div>
                    </article>
                  ))}</div> : <EmptyState icon={MemoryStick} title="No repository memories found" description="Add a note above or change the search to find saved knowledge." />}
                </section>
              )}

              {activeTab === "history" && (
                <section className="agent-tab-content">
                  <SectionHeading kicker="AUDIT TRAIL" title="Tool execution history" description="Review the read-only tool calls, exact inputs, outputs and specialist delegation outcomes." />
                  {executions.length ? <div className="agent-history-list">{executions.slice().reverse().map((execution) => {
                    const delegation = delegations.find((item) => item.source_execution_id === execution.id);
                    return <article className="agent-history-card panel" key={execution.id}>
                      <div className="agent-history-top"><div><strong>{execution.tool_name}</strong><span>#{shortId(execution.id)}</span></div><StatusPill value={execution.status} /></div>
                      <div className="agent-history-meta"><span>{delegation?.specialist_name || execution.tool_input?.specialist_name || "RepoLens agent"}</span><span>{formatDate(execution.created_at)}</span><span>{execution.duration_ms != null ? execution.duration_ms + " ms" : "Duration —"}</span></div>
                      <details><summary>View execution input and output</summary><div className="agent-code-block"><div>INPUT</div><pre>{JSON.stringify(execution.tool_input || {}, null, 2)}</pre></div>{execution.tool_output && <div className="agent-code-block"><div>OUTPUT</div><pre>{JSON.stringify(execution.tool_output, null, 2)}</pre></div>}{execution.error_message && <p className="agent-task-error">{execution.error_message}</p>}</details>
                    </article>;
                  })}</div> : <EmptyState icon={History} title="No tool executions yet" description="Once the task runs, its read-only tool calls and results will be recorded here." />}
                  {delegations.length > 0 && <div className="agent-delegation-summary panel"><strong>Specialist delegation log</strong>{delegations.map((item) => <div key={item.id}><span>{item.specialist_name}</span><span>{item.assignment_context?.step_key}</span><StatusPill value={item.status} /></div>)}</div>}
                </section>
              )}
            </>
          ) : (
            <div className="agent-task-welcome panel"><EmptyState icon={AlertCircle} title="Task could not be loaded" description="Refresh the task list and choose a task to inspect its execution workspace." /></div>
          )}
        </div>
      </div>
    </section>
  );
}
