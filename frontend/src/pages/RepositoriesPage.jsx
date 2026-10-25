import { Search, ArrowRight, Code2, GitBranch, GitFork, Github, Plus, ShieldCheck, Star, Trash2 } from "lucide-react";
import { useState } from "react";

export default function RepositoriesPage({ repositories, onConnect, onBrowse, onRemove }) {
  const [query, setQuery] = useState("");
  const filteredRepositories = repositories.filter((repository) => `${repository.full_name} ${repository.description || ""} ${repository.language || ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <section className="repository-page">
      <div className="repository-page-heading">
        <div><span className="eyebrow">GITHUB WORKSPACE</span><h1>Your repositories</h1><p>Inspect public repository metadata and explore its current file tree.</p></div>
        <div className="repository-heading-actions">
          <label className="repository-filter"><Search size={16} /><input type="search" aria-label="Filter repositories" placeholder="Filter repositories…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Connect repository</button>
        </div>
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
          {filteredRepositories.map((repository) => (
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
      {repositories.length > 0 && filteredRepositories.length === 0 && <div className="repository-empty panel"><h2>No matching repositories</h2><p>Try a different repository name, description, or language.</p><button className="button button-secondary button-small" type="button" onClick={() => setQuery("")}>Clear filter</button></div>}
      <div className="session-storage-note"><ShieldCheck size={16} /><span>Repository metadata, branch selection, source indexing, embeddings, and retrieval are available from Code explorer.</span></div>
    </section>
  );
}
