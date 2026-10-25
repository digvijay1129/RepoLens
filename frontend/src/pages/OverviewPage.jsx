import { ArrowRight, ArrowUpRight, Bot, CheckCircle2, Code2, FileSearch, GitBranch, Github, Layers3, Plus, Search, Sparkles } from "lucide-react";
import ApiStatus from "../components/common/ApiStatus.jsx";

const prompts = [
  "Where is authentication handled?",
  "Explain the main application flow",
  "Which files configure the database?",
];

function statusLabel(repository) {
  if (repository.embedding_status === "embedded") return "Semantic ready";
  if (repository.indexing_status === "indexed") return "Indexed";
  if (repository.indexing_status === "indexing") return "Indexing";
  return "Not indexed";
}

export default function OverviewPage({ apiStatus, onConnect, onPrompt, onNavigate, repositories, onBrowseRepository }) {
  const indexedCount = repositories.filter((repository) => repository.indexing_status === "indexed").length;
  const embeddedCount = repositories.filter((repository) => repository.embedding_status === "embedded").length;

  return (
    <section className="overview-dashboard animate-fade-in space-y-6">
      <header className="dashboard-heading flex flex-col items-start justify-between gap-5 md:flex-row md:items-center">
        <div>
          <span className="eyebrow"><span className="eyebrow-line" /> DEVELOPER WORKSPACE</span>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Your code workspace</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Review repositories, inspect source files, and ask questions grounded in your code.</p>
        </div>
        <div className="dashboard-actions flex w-full flex-wrap gap-2 md:w-auto">
          <button className="button button-secondary" type="button" onClick={() => onNavigate("explorer")}><Code2 size={16} /> Explore code</button>
          <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Connect repository</button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="dashboard-stat panel flex items-center gap-3 rounded-panel border border-border bg-surface p-4 shadow-panel transition-all duration-200">
          <span className="dashboard-stat-icon dashboard-stat-icon-violet"><Github size={19} /></span>
          <div><span className="block text-xs text-muted">Repositories</span><strong className="mt-1 block text-2xl font-bold tracking-tight text-foreground">{repositories.length}</strong></div>
        </article>
        <article className="dashboard-stat panel flex items-center gap-3 rounded-panel border border-border bg-surface p-4 shadow-panel transition-all duration-200">
          <span className="dashboard-stat-icon dashboard-stat-icon-blue"><FileSearch size={19} /></span>
          <div><span className="block text-xs text-muted">Source indexed</span><strong className="mt-1 block text-2xl font-bold tracking-tight text-foreground">{indexedCount}</strong></div>
        </article>
        <article className="dashboard-stat panel flex items-center gap-3 rounded-panel border border-border bg-surface p-4 shadow-panel transition-all duration-200">
          <span className="dashboard-stat-icon dashboard-stat-icon-mint"><Layers3 size={19} /></span>
          <div><span className="block text-xs text-muted">Semantic ready</span><strong className="mt-1 block text-2xl font-bold tracking-tight text-foreground">{embeddedCount}</strong></div>
        </article>
        <article className="dashboard-stat panel flex items-center gap-3 rounded-panel border border-border bg-surface p-4 shadow-panel transition-all duration-200">
          <span className="dashboard-stat-icon dashboard-stat-icon-neutral"><CheckCircle2 size={19} /></span>
          <div className="min-w-0"><span className="block text-xs text-muted">Backend status</span><div className="mt-2"><ApiStatus status={apiStatus} /></div></div>
        </article>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1.12fr)_minmax(320px,0.88fr)]">
        <section className="dashboard-panel panel min-w-0 overflow-hidden rounded-panel border border-border bg-surface shadow-panel">
          <header className="dashboard-panel-heading flex items-center justify-between gap-4 border-b border-border px-5 py-4">
            <div><h2 className="text-base font-bold text-foreground">Recent repositories</h2><p className="mt-1 text-xs text-muted">Your connected GitHub projects</p></div>
            <button className="icon-button" type="button" title="Browse repositories" aria-label="Browse repositories" onClick={() => onNavigate("repositories")}><Search size={17} /></button>
          </header>
          {repositories.length ? (
            <div className="dashboard-repository-list divide-y divide-border">
              {repositories.slice(0, 6).map((repository) => (
                <button className="dashboard-repository-row group flex w-full items-center gap-3 px-5 py-4 text-left transition-colors duration-150 hover:bg-surface-raised" key={repository.full_name} type="button" onClick={() => onBrowseRepository(repository.full_name)}>
                  <span className="dashboard-repo-icon"><Github size={17} /></span>
                  <span className="min-w-0 flex-1"><strong className="block truncate text-sm font-semibold text-foreground">{repository.full_name}</strong><span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted"><span>{repository.language || "Unknown language"}</span><span aria-hidden="true">·</span><span className="inline-flex items-center gap-1"><GitBranch size={12} />{repository.selected_branch || repository.default_branch || "main"}</span></span></span>
                  <span className={`repository-readiness ${repository.embedding_status === "embedded" ? "is-ready" : repository.indexing_status === "indexed" ? "is-indexed" : ""}`}>{statusLabel(repository)}</span>
                  <ArrowRight size={15} className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
                </button>
              ))}
              <div className="flex items-center justify-between gap-4 px-5 py-3"><span className="text-xs text-muted">Showing {Math.min(repositories.length, 6)} of {repositories.length}</span><button className="text-action" type="button" onClick={() => onNavigate("repositories")}>All repositories <ArrowRight size={14} /></button></div>
            </div>
          ) : (
            <div className="dashboard-empty flex flex-col items-center px-6 py-10 text-center">
              <span className="dashboard-empty-icon"><Github size={23} /></span>
              <h3 className="mt-4 text-sm font-bold text-foreground">No repositories yet</h3>
              <p className="mt-2 max-w-sm text-xs leading-6 text-muted">Connect a public repository to browse its files, index source chunks, and enable code-aware chat.</p>
              <button className="button button-primary mt-5" type="button" onClick={onConnect}><Plus size={15} /> Connect your first repository</button>
            </div>
          )}
        </section>

        <section className="dashboard-panel panel min-w-0 overflow-hidden rounded-panel border border-border bg-surface shadow-panel">
          <header className="dashboard-panel-heading flex items-center gap-3 border-b border-border px-5 py-4">
            <span className="dashboard-chat-icon"><Sparkles size={18} /></span>
            <div><h2 className="text-base font-bold text-foreground">Ask your codebase</h2><p className="mt-1 text-xs text-muted">Start with a common engineering question</p></div>
          </header>
          <div className="p-4 sm:p-5">
            <div className="prompt-list">
              {prompts.map((prompt, index) => (
                <button className="prompt-suggestion" type="button" key={prompt} onClick={() => onPrompt(prompt)}><span className="prompt-number">0{index + 1}</span><span>{prompt}</span><ArrowUpRight size={15} /></button>
              ))}
            </div>
            <div className="dashboard-chat-foot"><Bot size={15} /><span>Answers are grounded in indexed source code and can include file and line references.</span></div>
            <button className="text-action mt-4" type="button" onClick={() => onNavigate("conversations")}>Open AI chat <ArrowRight size={14} /></button>
          </div>
        </section>
      </div>

      <div className="dashboard-footer-note flex items-start gap-3 rounded-xl border border-border bg-surface-raised px-4 py-3">
        <span className="dashboard-footer-note-icon"><Sparkles size={16} /></span>
        <p className="m-0 text-xs leading-6 text-muted"><strong className="font-semibold text-foreground">Built around evidence.</strong> RepoLens uses retrieved source chunks to help you verify explanations instead of relying on ungrounded guesses.</p>
      </div>
    </section>
  );
}
