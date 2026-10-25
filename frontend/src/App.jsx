import { useEffect, useRef, useState } from "react";
import {
  Activity, AlertCircle, ArrowLeft, ArrowRight, ArrowUpRight, Bot, Check, ChevronDown,
  CircleHelp, Clock3, Code2, ExternalLink, FileCode2, Folder, FolderOpen, GitBranch,
  GitFork, Github, LayoutDashboard, LifeBuoy, LoaderCircle, LockKeyhole, LogIn, LogOut,
  Mail, Menu, MessageSquareText, Plus, Search, Settings2, ShieldCheck, Sparkles, Star,
  TerminalSquare, Trash2, UserRound, X,
} from "lucide-react";
import { clearAccessToken, getAccessToken, getApiHealth, getCurrentUser, getRepositoryBranches, getRepositoryContents, getRepositoryIndexingJob, getSavedRepositories, loginAccount, registerAccount, saveRepository, startRepositoryIndex, selectRepositoryBranch, deleteSavedRepository, setAccessToken } from "./lib/api.js";
import { normalizeGitHubRepositoryUrl } from "./lib/githubRepository.js";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "repositories", label: "Repositories", icon: Github },
  { id: "explorer", label: "Code explorer", icon: Code2, soon: true },
  { id: "conversations", label: "Conversations", icon: MessageSquareText, soon: true },
];

const prompts = [
  "Where is authentication handled?",
  "Explain the main application flow",
  "Which files configure the database?",
];

const pageDetails = {
  repositories: ["Your repositories", "Connect a GitHub project to prepare its source files for exploration."],
  explorer: ["Code explorer", "Browse indexed files and jump from answers to exact source lines."],
  conversations: ["Conversations", "Return to previous code questions and their source references."],
  settings: ["Workspace settings", "Manage preferences and integrations as they become available."],
};

function BrandMark() {
  return <div className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></div>;
}

function ApiStatus({ status }) {
  const label = { checking: "Checking API", connected: "API online", offline: "API offline" };
  return <div className={"api-status api-status--" + status} role="status" aria-live="polite"><span className="status-dot" />{label[status]}</div>;
}


function AuthScreen({ onAuthenticated, initialMessage = "" }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialMessage);

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      const session = mode === "register"
        ? await registerAccount({ email, password, display_name: displayName.trim() || undefined })
        : await loginAccount({ email, password });
      setAccessToken(session.access_token);
      await onAuthenticated(session);
    } catch (requestError) {
      setError(requestError?.message || "Unable to sign in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-brand">
        <span className="auth-brand-mark"><Code2 size={22} /></span>
        <span>RepoLens<small>CODEBASE INTELLIGENCE</small></span>
      </div>
      <div className="auth-layout">
        <section className="auth-intro">
          <span className="eyebrow"><span className="eyebrow-line" /> YOUR DEVELOPER WORKSPACE</span>
          <h1>Get closer to<br /><span>your codebase.</span></h1>
          <p>Connect public GitHub repositories, explore their file trees, and build toward source-grounded AI assistance in a workspace of your own.</p>
          <div className="auth-benefits">
            <span><ShieldCheck size={16} /> Your saved repositories stay scoped to your account</span>
            <span><Github size={16} /> Public GitHub browsing with no GitHub token</span>
            <span><GitBranch size={16} /> Remember the branch you are exploring</span>
          </div>
          <div className="auth-illustration"><div className="auth-illustration-ring" /><div className="auth-illustration-card"><div><span /><span /><span /><i>repository.py</i></div><code><b>def</b> retrieve_context(repo):</code><code>&nbsp;&nbsp;files = repo.<em>search</em>()</code><code>&nbsp;&nbsp;<b>return</b> files</code><small><span /> READY FOR YOUR REPOSITORY</small></div></div>
        </section>
        <section className="auth-card panel">
          <div className="auth-card-top"><span className="auth-card-icon"><LockKeyhole size={19} /></span><span className="auth-secure-pill"><span /> SECURE WORKSPACE</span></div>
          <span className="section-kicker">{mode === "login" ? "WELCOME BACK" : "CREATE YOUR ACCOUNT"}</span>
          <h2>{mode === "login" ? "Sign in to RepoLens" : "Create your workspace"}</h2>
          <p className="auth-card-subtitle">{mode === "login" ? "Continue exploring the repositories you have saved." : "Your own space for repository browsing and code intelligence."}</p>
          <div className="auth-mode-tabs" role="tablist" aria-label="Account access mode">
            <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Sign in</button>
            <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); }}>Create account</button>
          </div>
          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "register" && <label>Display name<div className="auth-input-wrap"><UserRound size={17} /><input autoComplete="name" maxLength={120} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="How should we address you?" /></div></label>}
            <label>Email address<div className="auth-input-wrap"><Mail size={17} /><input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" maxLength={320} /></div></label>
            <label>Password<div className="auth-input-wrap"><LockKeyhole size={17} /><input type="password" required autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === "register" ? "At least 12 characters" : "Enter your password"} /></div>{mode === "register" && <small className="auth-field-hint">Use at least 12 characters. Passwords are stored as Argon2 hashes, never as plaintext.</small>}</label>
            {error && <p className="field-error auth-error" role="alert"><AlertCircle size={15} />{error}</p>}
            <button aria-label={busy ? "Submitting account form" : mode === "login" ? "Submit sign in" : "Submit registration"} className="button button-primary button-full auth-submit" type="submit" disabled={busy}>{busy ? <><LoaderCircle className="spin" size={16} /> Please wait…</> : mode === "login" ? <>Sign in <LogIn size={16} /></> : <>Create account <ArrowRight size={16} /></>}</button>
          </form>
          <div className="auth-card-foot"><ShieldCheck size={15} /><span>Private account session · Public repositories only in this phase</span></div>
        </section>
      </div>
      <footer className="auth-footer"><span>© 2026 RepoLens</span><span><i /> Built for developers, with source-first principles</span></footer>
    </main>
  );
}

function ConnectModal({ onClose, onNotice, onConnectRepository }) {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [error, setError] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const dialogRef = useRef(null);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const dialog = dialogRef.current;
    dialog?.querySelector("#repository-url")?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab" || !dialog) return;
      const focusable = Array.from(
        dialog.querySelectorAll('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'),
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [onClose]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (isConnecting) return;
    setError("");

    let repository;
    try {
      repository = normalizeGitHubRepositoryUrl(repositoryUrl);
    } catch (validationError) {
      setError(validationError.message);
      return;
    }

    setIsConnecting(true);
    try {
      const metadata = await onConnectRepository(repository.canonicalUrl);
      setIsConnecting(false);
      onClose();
      onNotice(
        "Saved " + metadata.full_name +
        " to your workspace. Its metadata and selected branch are stored in PostgreSQL.",
      );
    } catch (connectionError) {
      setError(connectionError?.message || "Unable to inspect this public repository. Please retry.");
      setIsConnecting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="connect-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <button className="icon-button modal-close" type="button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button>
        <div className="modal-icon"><Github size={23} /></div>
        <span className="eyebrow">START WITH A REPOSITORY</span>
        <h2 id="modal-title">Bring your code into focus.</h2>
        <p className="muted-copy">Inspect a public GitHub repository and browse its live file tree. Private repositories are not supported yet.</p>
        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="repository-url">GitHub repository URL</label>
          <div className={"input-with-icon" + (error ? " input-with-icon--error" : "")}>
            <Github size={18} />
            <input id="repository-url" type="url" placeholder="https://github.com/owner/repository" value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} autoFocus aria-invalid={Boolean(error)} aria-describedby={error ? "repository-error" : "repository-help"} />
          </div>
          {error ? <p className="field-error" id="repository-error" role="alert"><AlertCircle size={14} />{error}</p> : <p className="field-help" id="repository-help">Public repositories first. Private repository authorization will come later.</p>}
          <div className="modal-note"><ShieldCheck size={17} /><span>RepoLens retrieves public metadata, then saves it to your authenticated workspace. No GitHub token is needed.</span></div>
          <button className="button button-primary button-full" type="submit" disabled={isConnecting}>{isConnecting ? <><LoaderCircle className="spin" size={16} /> Saving repository…</> : <>Save to workspace <ArrowRight size={16} /></>}</button>
        </form>
      </section>
    </div>
  );
}

function Sidebar({ active, onNavigate, onConnect, mobileOpen, onClose, currentUser }) {
  return (
    <>
      {mobileOpen && <button className="mobile-scrim" type="button" aria-label="Close menu" onClick={onClose} />}
      <aside className={"sidebar" + (mobileOpen ? " sidebar--open" : "")}>
        <div className="sidebar-brand">
          <BrandMark /><div className="brand-wordmark">repo<span>lens</span><sup>β</sup></div>
          <button className="icon-button sidebar-close" type="button" onClick={onClose} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="workspace-switcher"><div className="workspace-avatar">R</div><div className="workspace-copy"><span className="workspace-label">WORKSPACE</span><strong>My workspace</strong></div><ChevronDown size={15} className="workspace-chevron" /></div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={"nav-item" + (active === item.id ? " nav-item--active" : "")} type="button" onClick={() => { onNavigate(item.id); onClose(); }}>
              <Icon size={18} strokeWidth={1.8} /><span>{item.label}</span>
              {item.soon && <small className="nav-soon">SOON</small>}
              {active === item.id && <i className="nav-active-mark" />}
            </button>;
          })}
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-section-label">PERSONAL</div>
        <nav className="primary-nav" aria-label="Personal navigation">
          <button className={"nav-item" + (active === "settings" ? " nav-item--active" : "")} type="button" onClick={() => { onNavigate("settings"); onClose(); }}><Settings2 size={18} strokeWidth={1.8} /><span>Settings</span></button>
          <button className="nav-item" type="button" onClick={() => onNavigate("help")}><LifeBuoy size={18} strokeWidth={1.8} /><span>Help & support</span><ArrowUpRight size={14} className="nav-external" /></button>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-plan-card"><div className="plan-icon"><Sparkles size={17} /></div><strong>Your code, understood.</strong><p>Source-grounded insights for your next engineering task.</p><button type="button" className="plan-link" onClick={onConnect}>Add a repository <ArrowRight size={14} /></button></div>
          <div className="profile-row"><div className="profile-avatar">{(currentUser?.display_name || currentUser?.email || "D").slice(0, 1).toUpperCase()}</div><div className="profile-info"><strong>{currentUser?.display_name || "Developer"}</strong><span>{currentUser?.email || "Authenticated workspace"}</span></div><span className="profile-auth-dot" aria-label="Signed in" /></div>
        </div>
      </aside>
    </>
  );
}

function EmptyRepoArt() {
  return <div className="empty-illustration" aria-hidden="true">
    <div className="illustration-orbit orbit-one" /><div className="illustration-orbit orbit-two" />
    <div className="illustration-file file-back"><FileCode2 size={27} /></div><div className="illustration-file file-front"><Github size={31} /></div>
    <div className="illustration-spark spark-one"><Sparkles size={16} /></div><div className="illustration-spark spark-two"><Code2 size={15} /></div>
  </div>;
}

function Overview({ apiStatus, onConnect, onPrompt, onNavigate, repositories, onBrowseRepository }) {
  return <>
    <section className="welcome-row">
      <div className="welcome-copy">
        <div className="eyebrow welcome-eyebrow"><span className="eyebrow-line" /> CODEBASE INTELLIGENCE, REIMAGINED</div>
        <h1>Understand the code.<br /><span>Not just the syntax.</span></h1>
        <p className="welcome-subtitle">Your AI companion for navigating repositories, tracing logic, and getting answers grounded in the source.</p>
        <div className="welcome-actions"><button className="button button-primary" type="button" onClick={onConnect}><Plus size={17} /> Connect repository</button><button className="button button-secondary" type="button" onClick={() => onNavigate("explorer")}>Explore workspace <ArrowRight size={16} /></button></div>
        <div className="trust-row"><span><ShieldCheck size={15} /> Source-first answers</span><i className="trust-separator" /><span><GitBranch size={15} /> Repository-aware</span></div>
      </div>
      <div className="hero-art" aria-label="Abstract code intelligence illustration">
        <div className="hero-glow" /><div className="hero-ring ring-outer" /><div className="hero-ring ring-inner" />
        <div className="hero-code-card">
          <div className="code-card-top"><span /><span /><span /><i>repo_lens.py</i></div>
          <div className="code-lines">
            <div><b>01</b><span className="code-purple">def</span> <span className="code-blue">understand</span><span>(code):</span></div>
            <div><b>02</b><span className="code-indent">context =</span> <span className="code-green">retrieve</span>(code)</div>
            <div><b>03</b><span className="code-indent">answer =</span> <span className="code-green">explain</span>(context)</div>
            <div><b>04</b><span className="code-indent code-muted"># show the evidence</span></div>
            <div><b>05</b><span className="code-indent">return</span> answer</div>
          </div>
          <div className="code-card-footer"><span className="mini-pulse" /> GROUNDED IN YOUR CODE <span className="footer-check"><Check size={11} /></span></div>
        </div>
        <div className="floating-chip chip-source"><FileCode2 size={15} /><span>Source references</span><Check size={13} /></div>
        <div className="floating-chip chip-ai"><Sparkles size={15} /><span>Context-aware AI</span></div>
        <div className="hero-orbit-dot dot-a" /><div className="hero-orbit-dot dot-b" />
      </div>
    </section>

    <section className="section-heading">
      <div><span className="section-kicker">YOUR WORKSPACE</span><h2>A clearer view of your code</h2></div>
      <ApiStatus status={apiStatus} />
    </section>

    <section className="feature-grid" aria-label="RepoLens capabilities">
      <article className="feature-card"><div className="feature-icon feature-icon--violet"><Github size={19} /></div><div className="feature-meta"><span>01 / CONNECT</span><span className="feature-phase">PHASE 3</span></div><h3>Bring in a codebase</h3><p>Start from a GitHub repository. RepoLens will prepare its files and documentation for exploration.</p><button className="text-action" type="button" onClick={onConnect}>Connect a repository <ArrowRight size={15} /></button></article>
      <article className="feature-card"><div className="feature-icon feature-icon--blue"><Search size={19} /></div><div className="feature-meta"><span>02 / RETRIEVE</span><span className="feature-phase">PHASE 5</span></div><h3>Find the right context</h3><p>Combine semantic similarity and keyword search to locate relevant files, functions, and code paths.</p><button className="text-action" type="button" onClick={() => onNavigate("explorer")}>Preview code explorer <ArrowRight size={15} /></button></article>
      <article className="feature-card"><div className="feature-icon feature-icon--mint"><Bot size={19} /></div><div className="feature-meta"><span>03 / UNDERSTAND</span><span className="feature-phase">PHASE 6</span></div><h3>Ask better questions</h3><p>Get explanations supported by retrieved source code, with file paths and line-level references.</p><button className="text-action" type="button" onClick={() => onNavigate("conversations")}>Explore conversations <ArrowRight size={15} /></button></article>
    </section>

    <section className="lower-grid">
      <article className="panel repositories-panel">
        <div className="panel-heading"><div><span className="section-kicker">CONNECTED PROJECTS</span><h2>Recent repositories</h2></div><button className="icon-button panel-more" type="button" aria-label="Search repositories"><Search size={17} /></button></div>
        {repositories.length ? (
          <div className="connected-repo-list">
            {repositories.slice(0, 4).map((repository) => (
              <button className="connected-repo-row" key={repository.full_name} type="button" onClick={() => onBrowseRepository(repository.full_name)}>
                <span className="connected-repo-icon"><Github size={17} /></span>
                <span className="connected-repo-copy"><strong>{repository.full_name}</strong><small>{repository.language || "Language not detected"} · {repository.default_branch || "default branch unknown"}</small></span>
                <ArrowRight size={16} />
              </button>
            ))}
            <button className="text-action repo-list-action" type="button" onClick={() => onNavigate("repositories")}>View all repositories <ArrowRight size={15} /></button>
          </div>
        ) : (
          <div className="empty-state"><EmptyRepoArt /><h3>Your next codebase starts here.</h3><p>Connect a public GitHub repository to inspect its metadata and browse the live file tree.</p><button className="button button-secondary button-small" type="button" onClick={onConnect}><Plus size={15} /> Add repository</button></div>
        )}
      </article>
      <article className="panel ask-panel">
        <div className="panel-heading"><div><span className="section-kicker">ASK YOUR CODEBASE</span><h2>Start with a question</h2></div><div className="ask-icon"><Sparkles size={18} /></div></div>
        <p className="ask-intro">Once a repository is indexed, ask RepoLens how the pieces fit together.</p>
        <div className="prompt-list">{prompts.map((prompt, index) => <button className="prompt-suggestion" type="button" key={prompt} onClick={() => onPrompt(prompt)}><span className="prompt-number">0{index + 1}</span><span>{prompt}</span><ArrowUpRight size={15} /></button>)}</div>
        <div className="ask-coming"><div className="coming-indicator"><span /></div><span>RAG chat is planned for Phase 6</span><Sparkles size={14} /></div>
      </article>
    </section>

    <section className="bottom-note"><div className="bottom-note-icon"><ShieldCheck size={17} /></div><div><strong>Built around evidence, not guesses.</strong><p>RepoLens is being developed to link answers back to source files so you can verify every explanation.</p></div><div className="bottom-note-status"><span className="note-status-dot" /> Foundation stage</div></section>
  </>;
}


function RepositoriesPage({ repositories, onConnect, onBrowse, onRemove }) {
  return (
    <section className="repository-page">
      <div className="repository-page-heading">
        <div><span className="eyebrow">GITHUB WORKSPACE</span><h1>Your repositories</h1><p>Inspect public repository metadata and explore its current file tree.</p></div>
        <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Connect repository</button>
      </div>
      {repositories.length === 0 ? (
        <div className="repository-empty panel">
          <div className="placeholder-icon"><Github size={26} /></div>
          <h2>No repositories connected yet</h2>
          <p>Connect a public GitHub repository. RepoLens will fetch live metadata from GitHub and let you browse directories.</p>
          <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Connect a repository</button>
        </div>
      ) : (
        <div className="repository-card-grid">
          {repositories.map((repository) => (
            <article className="repository-card panel" key={repository.full_name}>
              <div className="repository-card-head"><span className="repository-card-icon"><Github size={20} /></span><span className="public-pill">PUBLIC REPOSITORY</span></div>
              <h2>{repository.full_name}</h2>
              <p>{repository.description || "No repository description provided."}</p>
              <div className="repository-stats">
                <span><Star size={14} /> {repository.stargazers_count}</span>
                <span><GitFork size={14} /> {repository.forks_count}</span>
                <span><Code2 size={14} /> {repository.language || "Unknown"}</span>
              </div>
              <div className="repository-card-foot"><span><GitBranch size={14} /> {repository.selected_branch || repository.default_branch}</span><div className="repository-card-actions"><button className="button button-secondary button-small" type="button" onClick={() => onBrowse(repository.full_name)}>Browse code <ArrowRight size={14} /></button><button className="icon-button repository-remove-button" type="button" aria-label={"Remove " + repository.full_name} title="Remove repository" onClick={() => onRemove(repository.id)}><Trash2 size={15} /></button></div></div>
            </article>
          ))}
        </div>
      )}
      <div className="session-storage-note"><ShieldCheck size={16} /><span>Repository metadata and branch selection are saved to your authenticated workspace. Source files still open on GitHub until indexing is implemented.</span></div>
    </section>
  );
}

function RepositoryExplorer({ repositories, selectedRepositoryKey, onSelectRepository, onConnect, onRepositoryUpdated }) {
  const selectedRepository = repositories.find((repository) => repository.full_name === selectedRepositoryKey) || repositories[0] || null;
  const [path, setPath] = useState("");
  const [contents, setContents] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [branches, setBranches] = useState([]);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [branchSaving, setBranchSaving] = useState(false);
  const [branchError, setBranchError] = useState("");
  const [indexJob, setIndexJob] = useState(null);
  const [indexStarting, setIndexStarting] = useState(false);
  const [indexError, setIndexError] = useState("");
  const selectedBranch = selectedRepository?.selected_branch || selectedRepository?.default_branch || "main";
  const indexIsActive = indexJob && ["queued", "running"].includes(indexJob.status);

  useEffect(() => {
    let cancelled = false;
    if (!selectedRepository?.id) {
      setBranches([]);
      setBranchError("");
      setBranchesLoading(false);
      return undefined;
    }
    setBranchesLoading(true);
    setBranches([]);
    setBranchError("");
    getRepositoryBranches(selectedRepository.id).then((result) => {
      if (!cancelled) setBranches(result.items || []);
    }).catch((requestError) => {
      if (!cancelled) setBranchError(requestError?.message || "Unable to load repository branches.");
    }).finally(() => {
      if (!cancelled) setBranchesLoading(false);
    });
    return () => { cancelled = true; };
  }, [selectedRepository?.id]);

  async function handleBranchChange(event) {
    const nextBranch = event.target.value;
    if (!selectedRepository?.id || !nextBranch || nextBranch === selectedBranch) return;
    setBranchSaving(true);
    setBranchError("");
    try {
      const updatedRepository = await selectRepositoryBranch(selectedRepository.id, nextBranch);
      onRepositoryUpdated(updatedRepository);
      setPath("");
      setContents(null);
    } catch (requestError) {
      setBranchError(requestError?.message || "Unable to save the selected branch.");
    } finally {
      setBranchSaving(false);
    }
  }


  async function handleStartIndexing() {
    if (!selectedRepository?.id || indexStarting || indexIsActive) return;
    setIndexStarting(true);
    setIndexError("");
    try {
      const job = await startRepositoryIndex(selectedRepository.id);
      setIndexJob(job);
    } catch (requestError) {
      setIndexError(requestError?.message || "Unable to start source indexing.");
    } finally {
      setIndexStarting(false);
    }
  }

  useEffect(() => {
    if (!indexJob || !["queued", "running"].includes(indexJob.status) || !selectedRepository?.id) {
      return undefined;
    }
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const latest = await getRepositoryIndexingJob(selectedRepository.id, indexJob.id);
        if (cancelled) return;
        if (["completed", "failed"].includes(latest.status)) {
          try {
            const savedRepositories = await getSavedRepositories();
            if (cancelled) return;
            const updated = savedRepositories.find((repository) => repository.id === selectedRepository.id);
            if (updated) onRepositoryUpdated(updated);
          } catch {
            // Job status remains available even if the workspace refresh temporarily fails.
          }
          if (!cancelled) setIndexJob(latest);
        } else {
          setIndexJob(latest);
          timer = window.setTimeout(poll, 1500);
        }
      } catch (requestError) {
        if (cancelled) return;
        setIndexError(requestError?.message || "Unable to refresh indexing progress.");
        timer = window.setTimeout(poll, 3000);
      }
    };
    timer = window.setTimeout(poll, 1000);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [indexJob?.id, indexJob?.status, selectedRepository?.id, onRepositoryUpdated]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedRepository) {
      setContents(null);
      setError("");
      setLoading(false);
      return undefined;
    }

    const parts = selectedRepository.full_name.split("/");
    if (parts.length !== 2) {
      setError("The repository name returned by GitHub is invalid.");
      return undefined;
    }

    setLoading(true);
    setError("");
    getRepositoryContents(parts[0], parts[1], {
      path,
      ref: selectedBranch,
    }).then((result) => {
      if (!cancelled) setContents(result);
    }).catch((requestError) => {
      if (!cancelled) {
        setError(requestError?.message || "Unable to load this directory.");
        setContents(null);
      }
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [selectedRepository?.full_name, selectedRepository?.selected_branch, selectedRepository?.default_branch, selectedBranch, path, refreshKey]);

  if (!selectedRepository) {
    return (
      <section className="repository-page">
        <div className="repository-page-heading"><div><span className="eyebrow">SOURCE BROWSER</span><h1>Code explorer</h1><p>Browse the actual file and directory listing of a public GitHub repository.</p></div></div>
        <div className="repository-empty panel">
          <div className="placeholder-icon"><FolderOpen size={26} /></div><h2>Choose a repository to explore</h2>
          <p>Connect a public repository first. Directory listings will be retrieved live from GitHub.</p>
          <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Connect repository</button>
        </div>
      </section>
    );
  }

  const parts = selectedRepository.full_name.split("/");
  const pathParts = path ? path.split("/") : [];
  const entries = [...(contents?.items || [])].sort((left, right) => {
    const leftDirectory = left.type === "dir" ? 0 : 1;
    const rightDirectory = right.type === "dir" ? 0 : 1;
    return leftDirectory - rightDirectory || left.name.localeCompare(right.name);
  });

  return (
    <section className="repository-page">
      <div className="repository-page-heading">
        <div><span className="eyebrow">SOURCE BROWSER</span><h1>Code explorer</h1><p>Navigate a public repository's actual directory tree, fetched from GitHub.</p></div>
        <div className="repo-heading-actions">
          <button className="button button-secondary" type="button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}><Activity size={16} /> Refresh</button>
          <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Add repository</button>
        </div>
      </div>

      <div className="repository-summary panel">
        <div className="repository-summary-main"><span className="repository-card-icon"><Github size={22} /></span><div><h2>{selectedRepository.full_name}</h2><p>{selectedRepository.description || "No repository description provided."}</p><a href={selectedRepository.canonical_url} target="_blank" rel="noreferrer">Open on GitHub <ExternalLink size={13} /></a></div></div>
        {repositories.length > 1 && <label className="repo-switcher-label">Repository<select aria-label="Select repository" value={selectedRepository.full_name} onChange={(event) => { onSelectRepository(event.target.value); setPath(""); }}><option value="">Select a repository</option>{repositories.map((repository) => <option key={repository.full_name} value={repository.full_name}>{repository.full_name}</option>)}</select></label>}
        <div className="repository-summary-stats"><span><GitBranch size={14} /> {selectedRepository.default_branch}</span><span><Code2 size={14} /> {selectedRepository.language || "Unknown language"}</span><span><Star size={14} /> {selectedRepository.stargazers_count} stars</span><span><GitFork size={14} /> {selectedRepository.forks_count} forks</span></div>
      </div>


      <div className="indexing-panel panel">
        <div className="indexing-panel-heading">
          <div className="indexing-title-block">
            <span className="indexing-icon"><Sparkles size={17} /></span>
            <div><h2>Source indexing</h2><p>Fetch safe text files, split them into source-aware chunks, and save a versioned snapshot for later retrieval.</p></div>
          </div>
          <span className={"index-status-pill index-status-" + (indexJob?.status || selectedRepository.indexing_status || "pending")}>
            {indexJob?.status || selectedRepository.indexing_status || "pending"}
          </span>
        </div>
        <div className="indexing-panel-actions">
          <div className="indexing-boundary-note"><ShieldCheck size={15} /><span>Never executes repository code. Files, size and total indexed bytes are bounded.</span></div>
          <button className="button button-primary" type="button" onClick={handleStartIndexing} disabled={!selectedRepository.id || indexStarting || Boolean(indexIsActive)}>
            {indexStarting || indexIsActive ? <><LoaderCircle className="spin" size={15} /> Indexing…</> : selectedRepository.indexing_status === "indexed" ? <>Re-index source <ArrowRight size={15} /></> : <>Index source files <ArrowRight size={15} /></>}
          </button>
        </div>
        {indexError && <p className="field-error indexing-error" role="alert"><AlertCircle size={14} />{indexError}</p>}
        {indexJob && <div className="indexing-job-details">
          <div className="indexing-job-message"><span>{indexJob.progress_message}</span><strong>{indexJob.processed_files}/{indexJob.total_files} files</strong></div>
          <progress className="index-progress-bar" max={Math.max(indexJob.total_files || 0, 1)} value={Math.min(indexJob.processed_files || 0, Math.max(indexJob.total_files || 0, 1))} aria-label="Indexing progress" />
          <div className="indexing-job-metrics">
            <span><strong>{indexJob.chunk_count || 0}</strong> chunks</span>
            <span><strong>{indexJob.skipped_files || 0}</strong> skipped files</span>
            {indexJob.commit_sha && <span>Commit <code>{indexJob.commit_sha.slice(0, 7)}</code></span>}
          </div>
          {indexJob.error_message && <p className="field-error indexing-error" role="alert"><AlertCircle size={14} />{indexJob.error_message}</p>}
        </div>}
      </div>

      <div className="file-browser panel">
        <div className="file-browser-heading">
          <div><span className="section-kicker">REPOSITORY FILES</span><h2>{path || "Repository root"}</h2></div>
          <label className="branch-select-label"><span><GitBranch size={13} /> Branch</span><select aria-label="Select branch" value={selectedBranch} onChange={handleBranchChange} disabled={branchesLoading || branchSaving || branches.length === 0}><option value={selectedBranch}>{selectedBranch}</option>{branches.filter((branch) => branch.name !== selectedBranch).map((branch) => <option key={branch.name} value={branch.name}>{branch.name}</option>)}</select>{branchesLoading && <LoaderCircle className="spin branch-loading" size={13} />}</label>
        </div>
        {branchError && <p className="field-error branch-error" role="alert"><AlertCircle size={14} />{branchError}</p>}
        <div className="file-breadcrumbs" aria-label="Directory breadcrumbs">
          <button type="button" onClick={() => setPath("")} className={!path ? "breadcrumb-current" : ""}>root</button>
          {pathParts.map((segment, index) => <span className="file-breadcrumb-part" key={pathParts.slice(0, index + 1).join("/")}><span>/</span><button type="button" onClick={() => setPath(pathParts.slice(0, index + 1).join("/"))} className={index === pathParts.length - 1 ? "breadcrumb-current" : ""}>{segment}</button></span>)}
        </div>

        {loading ? (
          <div className="file-browser-state"><LoaderCircle className="spin" size={24} /><strong>Loading directory</strong><span>Fetching the current file listing from GitHub…</span></div>
        ) : error ? (
          <div className="file-browser-state file-browser-state--error"><AlertCircle size={25} /><strong>Could not load this directory</strong><span>{error}</span><button className="button button-secondary button-small" type="button" onClick={() => setRefreshKey((value) => value + 1)}>Try again</button></div>
        ) : (
          <>
            {contents?.notice && <div className="directory-notice"><AlertCircle size={14} />{contents.notice}</div>}
            {path && <button type="button" className="file-row file-parent-row" onClick={() => setPath(pathParts.slice(0, -1).join("/"))}><span className="file-row-icon"><ArrowLeft size={16} /></span><span className="file-row-name">.. <small>Parent directory</small></span></button>}
            {entries.length === 0 ? <div className="file-browser-state"><FolderOpen size={24} /><strong>This directory is empty</strong><span>No entries were returned by GitHub for this path.</span></div> : (
              <div className="file-list">
                {entries.map((item) => {
                  const isDirectory = item.type === "dir";
                  const Icon = isDirectory ? Folder : FileCode2;
                  return isDirectory ? (
                    <button key={item.path} type="button" className="file-row" onClick={() => setPath(item.path)}>
                      <span className="file-row-icon file-row-icon--folder"><Icon size={17} /></span><span className="file-row-name">{item.name}<small>Directory</small></span><ArrowRight size={15} className="file-row-action" />
                    </button>
                  ) : (
                    <a key={item.path} className="file-row" href={item.html_url || selectedRepository.canonical_url} target="_blank" rel="noreferrer">
                      <span className="file-row-icon"><Icon size={16} /></span><span className="file-row-name">{item.name}<small>{item.type === "file" ? (item.size == null ? "File" : (item.size.toLocaleString() + " bytes")) : item.type}</small></span><ExternalLink size={14} className="file-row-action" />
                    </a>
                  );
                })}
              </div>
            )}
            <div className="file-browser-foot">{entries.length} item{entries.length === 1 ? "" : "s"} · File contents open on GitHub in this phase</div>
          </>
        )}
      </div>
    </section>
  );
}

function FuturePage({ page, onConnect }) {
  const detail = pageDetails[page] || pageDetails.repositories;
  return <section className="placeholder-page"><div className="placeholder-icon"><TerminalSquare size={26} /></div><span className="eyebrow">WORKSPACE IN PROGRESS</span><h1>{detail[0]}</h1><p>{detail[1]}</p><div className="placeholder-status"><Clock3 size={16} /> Scheduled for a later implementation phase</div><button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Start with a repository</button></section>;
}

export default function App() {
  const [activeNav, setActiveNav] = useState("overview");
  const [repositories, setRepositories] = useState([]);
  const [selectedRepositoryKey, setSelectedRepositoryKey] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [authStatus, setAuthStatus] = useState("checking");
  const [authMessage, setAuthMessage] = useState("");
  const [apiStatus, setApiStatus] = useState("checking");
  const [connectOpen, setConnectOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let mounted = true;
    getApiHealth().then((payload) => {
      if (mounted) setApiStatus(payload.status === "ok" ? "connected" : "offline");
    }).catch(() => {
      if (mounted) setApiStatus("offline");
    });

    if (!getAccessToken()) {
      setAuthStatus("signed-out");
    } else {
      Promise.all([getCurrentUser(), getSavedRepositories()]).then(([user, savedRepositories]) => {
        if (!mounted) return;
        setCurrentUser(user);
        setRepositories(savedRepositories);
        setSelectedRepositoryKey(savedRepositories[0]?.full_name || "");
        setAuthStatus("authenticated");
      }).catch((requestError) => {
        if (!mounted) return;
        clearAccessToken();
        setRepositories([]);
        setCurrentUser(null);
        setAuthMessage(requestError?.message || "Please sign in to continue.");
        setAuthStatus("signed-out");
      });
    }
    return () => { mounted = false; };
  }, []);

  async function handleAuthenticated(session) {
    setCurrentUser(session.user);
    setAuthStatus("authenticated");
    setAuthMessage("");
    try {
      const savedRepositories = await getSavedRepositories();
      setRepositories(savedRepositories);
      setSelectedRepositoryKey(savedRepositories[0]?.full_name || "");
    } catch (requestError) {
      setNotice(requestError?.message || "Signed in, but repositories could not be loaded.");
    }
  }

  async function connectRepository(repositoryUrl) {
    const saved = await saveRepository(repositoryUrl);
    setRepositories((current) => {
      const existingIndex = current.findIndex((repository) => repository.id === saved.id || repository.full_name.toLowerCase() === saved.full_name.toLowerCase());
      if (existingIndex < 0) return [...current, saved];
      return current.map((repository, index) => index === existingIndex ? saved : repository);
    });
    setSelectedRepositoryKey(saved.full_name);
    setActiveNav("explorer");
    return saved;
  }

  async function removeRepository(repositoryId) {
    try {
      await deleteSavedRepository(repositoryId);
      const nextRepositories = repositories.filter((repository) => repository.id !== repositoryId);
      setRepositories(nextRepositories);
      if (nextRepositories.length === 0 || !nextRepositories.some((repository) => repository.full_name === selectedRepositoryKey)) {
        setSelectedRepositoryKey(nextRepositories[0]?.full_name || "");
      }
      if (!nextRepositories.some((repository) => repository.full_name === selectedRepositoryKey)) setActiveNav("repositories");
      setNotice("Repository removed from your workspace.");
    } catch (requestError) {
      setNotice(requestError?.message || "Unable to remove this repository.");
    }
  }

  function updateRepository(updatedRepository) {
    setRepositories((current) => current.map((repository) => repository.id === updatedRepository.id ? updatedRepository : repository));
    setSelectedRepositoryKey(updatedRepository.full_name);
  }

  function signOut() {
    clearAccessToken();
    setCurrentUser(null);
    setRepositories([]);
    setSelectedRepositoryKey("");
    setAuthMessage("");
    setAuthStatus("signed-out");
    setNotice("");
  }

  function navigate(next, repositoryKey) {
    if (next === "help") {
      setNotice("Setup and verification instructions are available in docs/PHASE_3A.md.");
      return;
    }
    if (repositoryKey) setSelectedRepositoryKey(repositoryKey);
    setActiveNav(next);
  }

  const isOverview = activeNav === "overview";
  const pageTitle = isOverview ? "Overview" : (pageDetails[activeNav] ? pageDetails[activeNav][0] : "Help & support");

  if (authStatus === "checking") {
    return <main className="auth-loading"><span className="auth-brand-mark"><Code2 size={22} /></span><LoaderCircle className="spin" size={20} /><p>Loading your RepoLens workspace…</p></main>;
  }
  if (authStatus !== "authenticated") {
    return <AuthScreen initialMessage={authMessage} onAuthenticated={handleAuthenticated} />;
  }

  return <div className="app-shell">
    <Sidebar active={activeNav} onNavigate={navigate} onConnect={() => setConnectOpen(true)} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} currentUser={currentUser} />
    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-left"><button className="icon-button mobile-menu-button" type="button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{pageTitle}</strong></div></div>
        <div className="topbar-actions"><div className="environment-pill"><span /> AUTHENTICATED WORKSPACE</div><button className="icon-button topbar-help" type="button" onClick={() => setNotice("Setup and verification instructions are available in docs/PHASE_3B.md.")} aria-label="Help"><CircleHelp size={18} /></button><span className="current-user-email">{currentUser?.email}</span><div className="topbar-divider" /><button className="icon-button sign-out-button" type="button" onClick={signOut} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button></div>
      </header>
      <div className="page-content">
        {isOverview ? (
          <Overview
            apiStatus={apiStatus}
            repositories={repositories}
            onConnect={() => setConnectOpen(true)}
            onPrompt={(prompt) => setNotice("Question suggestion preview: repository retrieval and AI chat will be connected in Phase 6.")}
            onNavigate={navigate}
            onBrowseRepository={(repositoryKey) => navigate("explorer", repositoryKey)}
          />
        ) : activeNav === "repositories" ? (
          <RepositoriesPage
            repositories={repositories}
            onConnect={() => setConnectOpen(true)}
            onBrowse={(repositoryKey) => navigate("explorer", repositoryKey)}
            onRemove={removeRepository}
          />
        ) : activeNav === "explorer" ? (
          <RepositoryExplorer
            key={selectedRepositoryKey || "no-selected-repository"}
            repositories={repositories}
            selectedRepositoryKey={selectedRepositoryKey}
            onSelectRepository={setSelectedRepositoryKey}
            onRepositoryUpdated={updateRepository}
            onConnect={() => setConnectOpen(true)}
          />
        ) : (
          <FuturePage page={activeNav} onConnect={() => setConnectOpen(true)} />
        )}
        <footer className="app-footer"><span>© 2026 RepoLens <i className="footer-separator">·</i> Built for developers</span><span><i className="footer-health-dot" />{apiStatus === "connected" ? "API connected" : apiStatus === "checking" ? "Checking backend" : "Backend unavailable"}</span></footer>
      </div>
    </main>
    {notice && <div className="toast" role="status" aria-live="polite"><div className="toast-icon"><Check size={16} /></div><p>{notice}</p><button className="icon-button toast-close" type="button" onClick={() => setNotice("")} aria-label="Dismiss notification"><X size={16} /></button></div>}
    {connectOpen && <ConnectModal onClose={() => setConnectOpen(false)} onNotice={setNotice} onConnectRepository={connectRepository} />}
  </div>;
}
