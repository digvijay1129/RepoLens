import { useEffect, useState } from "react";
import {
  Activity, AlertCircle, ArrowRight, ArrowUpRight, Bot, Check, ChevronDown,
  CircleHelp, Clock3, Code2, FileCode2, GitBranch, Github, LayoutDashboard,
  LifeBuoy, Menu, MessageSquareText, Plus, Search, Settings2, ShieldCheck,
  Sparkles, TerminalSquare, X,
} from "lucide-react";
import { getApiHealth } from "./lib/api.js";

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

function ConnectModal({ onClose, onNotice }) {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    setError("");
    let parsed;
    try {
      parsed = new URL(repositoryUrl.trim());
    } catch {
      setError("Enter a valid GitHub repository URL.");
      return;
    }
    const parts = parsed.pathname.split("/").filter(Boolean);
    if (parsed.protocol !== "https:" || parsed.hostname.toLowerCase() !== "github.com" || parts.length < 2 || parts.some((part) => part === "." || part === "..")) {
      setError("Use a repository URL like https://github.com/owner/repository.");
      return;
    }
    onClose();
    onNotice("The URL format is valid. GitHub connection and indexing are planned for Phase 3; nothing has been stored yet.");
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="connect-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <button className="icon-button modal-close" type="button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button>
        <div className="modal-icon"><Github size={23} /></div>
        <span className="eyebrow">START WITH A REPOSITORY</span>
        <h2 id="modal-title">Bring your code into focus.</h2>
        <p className="muted-copy">Connect a GitHub project to prepare for indexing, code search, and grounded answers.</p>
        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="repository-url">GitHub repository URL</label>
          <div className={"input-with-icon" + (error ? " input-with-icon--error" : "")}>
            <Github size={18} />
            <input id="repository-url" type="url" placeholder="https://github.com/owner/repository" value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} autoFocus aria-describedby={error ? "repository-error" : "repository-help"} />
          </div>
          {error ? <p className="field-error" id="repository-error"><AlertCircle size={14} />{error}</p> : <p className="field-help" id="repository-help">Public repositories first. Private repository authorization will come later.</p>}
          <div className="modal-note"><ShieldCheck size={17} /><span>Phase 1 preview: this checks the URL format only. It will not access or save repository data.</span></div>
          <button className="button button-primary button-full" type="submit">Validate repository URL <ArrowRight size={16} /></button>
        </form>
      </section>
    </div>
  );
}

function Sidebar({ active, onNavigate, onConnect, mobileOpen, onClose }) {
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
          <div className="profile-row"><div className="profile-avatar">DR</div><div className="profile-info"><strong>Developer</strong><span>Local workspace</span></div><button className="icon-button profile-menu" type="button" aria-label="Profile menu"><Settings2 size={16} /></button></div>
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

function Overview({ apiStatus, onConnect, onPrompt, onNavigate }) {
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
        <div className="empty-state"><EmptyRepoArt /><h3>Your next codebase starts here.</h3><p>Connect a GitHub repository to prepare its source files for search and AI-assisted exploration.</p><button className="button button-secondary button-small" type="button" onClick={onConnect}><Plus size={15} /> Add repository</button></div>
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

function FuturePage({ page, onConnect }) {
  const detail = pageDetails[page] || pageDetails.repositories;
  return <section className="placeholder-page"><div className="placeholder-icon"><TerminalSquare size={26} /></div><span className="eyebrow">WORKSPACE IN PROGRESS</span><h1>{detail[0]}</h1><p>{detail[1]}</p><div className="placeholder-status"><Clock3 size={16} /> Scheduled for a later implementation phase</div><button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Start with a repository</button></section>;
}

export default function App() {
  const [activeNav, setActiveNav] = useState("overview");
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
    return () => { mounted = false; };
  }, []);

  function navigate(next) {
    if (next === "help") {
      setNotice("Setup and verification instructions are available in docs/PHASE_1.md.");
      return;
    }
    setActiveNav(next);
  }

  const isOverview = activeNav === "overview";
  const pageTitle = isOverview ? "Overview" : (pageDetails[activeNav] ? pageDetails[activeNav][0] : "Help & support");

  return <div className="app-shell">
    <Sidebar active={activeNav} onNavigate={navigate} onConnect={() => setConnectOpen(true)} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-left"><button className="icon-button mobile-menu-button" type="button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{pageTitle}</strong></div></div>
        <div className="topbar-actions"><div className="environment-pill"><span /> LOCAL PREVIEW</div><button className="icon-button topbar-help" type="button" onClick={() => setNotice("RepoLens is being built phase by phase. See docs/PHASE_1.md for the current scope.")} aria-label="Help"><CircleHelp size={18} /></button><div className="topbar-divider" /><button className="profile-avatar topbar-avatar" type="button" aria-label="Current local workspace">DR</button></div>
      </header>
      <div className="page-content">
        {isOverview ? <Overview apiStatus={apiStatus} onConnect={() => setConnectOpen(true)} onPrompt={(prompt) => setNotice("Question suggestion preview: repository retrieval and AI chat will be connected in Phase 6.")} onNavigate={setActiveNav} /> : <FuturePage page={activeNav} onConnect={() => setConnectOpen(true)} />}
        <footer className="app-footer"><span>© 2026 RepoLens <i className="footer-separator">·</i> Built for developers</span><span><i className="footer-health-dot" />{apiStatus === "connected" ? "API connected" : apiStatus === "checking" ? "Checking backend" : "Backend unavailable"}</span></footer>
      </div>
    </main>
    {notice && <div className="toast" role="status" aria-live="polite"><div className="toast-icon"><Check size={16} /></div><p>{notice}</p><button className="icon-button toast-close" type="button" onClick={() => setNotice("")} aria-label="Dismiss notification"><X size={16} /></button></div>}
    {connectOpen && <ConnectModal onClose={() => setConnectOpen(false)} onNotice={setNotice} />}
  </div>;
}
