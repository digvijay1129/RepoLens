import { Activity, AlertCircle, ArrowLeft, ArrowRight, ArrowUpRight, Check, Code2, ExternalLink, FileCode2, Folder, FolderOpen, GitBranch, GitFork, Github, LoaderCircle, Plus, Search, ShieldCheck, Sparkles, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { getRepositoryBranches, getRepositoryContents, getRepositoryIndexingJob, getSavedRepositories, selectRepositoryBranch, startRepositoryIndex, startRepositoryEmbeddings, searchSavedRepository } from "../lib/api.js";
import RepositoryChatPanel from "../components/chat/RepositoryChatPanel.jsx";

export default function CodeExplorerPage({ repositories, selectedRepositoryKey, onSelectRepository, onConnect, onRepositoryUpdated }) {
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
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState("hybrid");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searchPayload, setSearchPayload] = useState(null);
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

  async function handleStartEmbeddings() {
    if (
      !selectedRepository?.id
      || selectedRepository.indexing_status !== "indexed"
      || indexStarting
      || indexIsActive
    ) return;
    setIndexStarting(true);
    setIndexError("");
    try {
      const job = await startRepositoryEmbeddings(selectedRepository.id);
      setIndexJob(job);
    } catch (requestError) {
      setIndexError(requestError?.message || "Unable to start embedding generation.");
    } finally {
      setIndexStarting(false);
    }
  }
  async function handleSearchSubmit(event) {
    event.preventDefault();
    if (!selectedRepository?.id || !searchQuery.trim() || searchLoading) return;
    setSearchLoading(true);
    setSearchError("");
    try {
      const result = await searchSavedRepository(selectedRepository.id, {
        query: searchQuery.trim(),
        mode: searchMode,
        limit: 8,
      });
      setSearchPayload(result);
    } catch (requestError) {
      setSearchPayload(null);
      setSearchError(requestError?.message || "Unable to search this repository.");
    } finally {
      setSearchLoading(false);
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
            <div><h2>Source &amp; embedding pipeline</h2><p>Build a bounded source snapshot first, then generate model embeddings for source-aware semantic retrieval.</p></div>
          </div>
          <div className="index-status-group">
            <span className={"index-status-pill index-status-" + (selectedRepository.indexing_status || "pending")}>SOURCE: {selectedRepository.indexing_status || "pending"}</span>
            <span className={"index-status-pill index-status-" + (selectedRepository.embedding_status || "pending")}>EMBEDDINGS: {selectedRepository.embedding_status || "pending"}</span>
          </div>
        </div>
        <div className="indexing-panel-actions">
          <div className="indexing-boundary-note"><ShieldCheck size={15} /><span>Source code is never executed. Embedding generation sends eligible source text to your configured provider; API keys stay on the backend.</span></div>
          <div className="indexing-button-group">
            <button className="button button-secondary" type="button" onClick={handleStartIndexing} disabled={!selectedRepository.id || indexStarting || Boolean(indexIsActive)}>
              {indexStarting && indexJob?.job_type !== "embedding" || indexJob?.job_type === "source_indexing" && indexIsActive ? <><LoaderCircle className="spin" size={15} /> Indexing…</> : selectedRepository.indexing_status === "indexed" ? <>Re-index source <ArrowRight size={15} /></> : <>Index source files <ArrowRight size={15} /></>}
            </button>
            <button className="button button-primary" type="button" onClick={handleStartEmbeddings} disabled={!selectedRepository.id || selectedRepository.indexing_status !== "indexed" || indexStarting || Boolean(indexIsActive)}>
              {indexStarting && indexJob?.job_type === "embedding" || indexJob?.job_type === "embedding" && indexIsActive ? <><LoaderCircle className="spin" size={15} /> Generating…</> : selectedRepository.embedding_status === "embedded" ? <>Re-generate embeddings <Sparkles size={15} /></> : <>Generate embeddings <ArrowRight size={15} /></>}
            </button>
          </div>
        </div>
        {indexError && <p className="field-error indexing-error" role="alert"><AlertCircle size={14} />{indexError}</p>}
        {indexJob && <div className="indexing-job-details">
          <div className="indexing-job-message"><span className={"index-status-pill index-status-" + indexJob.status}>{indexJob.status}</span><span>{indexJob.progress_message}</span><strong>{indexJob.processed_files}/{indexJob.total_files} {indexJob.job_type === "embedding" ? "chunks" : "files"}</strong></div>
          <progress className="index-progress-bar" max={Math.max(indexJob.total_files || 0, 1)} value={Math.min(indexJob.processed_files || 0, Math.max(indexJob.total_files || 0, 1))} aria-label={indexJob.job_type === "embedding" ? "Embedding progress" : "Indexing progress"} />
          <div className="indexing-job-metrics">
            {indexJob.job_type === "embedding" ? <span><strong>{indexJob.processed_files || 0}</strong> embedded chunks</span> : <span><strong>{indexJob.chunk_count || 0}</strong> chunks</span>}
            <span><strong>{indexJob.skipped_files || 0}</strong> skipped {indexJob.job_type === "embedding" ? "chunks" : "files"}</span>
            {indexJob.embedding_model && <span>Model <code>{indexJob.embedding_model}</code></span>}
            {indexJob.embedding_dimensions && <span><strong>{indexJob.embedding_dimensions}</strong> dimensions</span>}
            {indexJob.commit_sha && <span>Commit <code>{indexJob.commit_sha.slice(0, 7)}</code></span>}
          </div>
          {indexJob.error_message && <p className="field-error indexing-error" role="alert"><AlertCircle size={14} />{indexJob.error_message}</p>}
        </div>}
        {selectedRepository.embedding_status === "embedded" && selectedRepository.embedding_model && <p className="embedding-active-meta"><Check size={14} /> Active embedding configuration: <strong>{selectedRepository.embedding_provider}</strong> / <strong>{selectedRepository.embedding_model}</strong> · {selectedRepository.embedding_dimensions} dimensions</p>}
      </div>

      <section className="source-search-panel panel" aria-labelledby="source-search-title">
        <div className="source-search-heading">
          <div className="source-search-heading-icon"><Search size={17} /></div>
          <div><h2 id="source-search-title">Search this codebase</h2><p>Find relevant source chunks with line-level citations from the current indexed commit.</p></div>
          <span className="search-engine-pill">PGVECTOR + FULL TEXT</span>
        </div>
        <form className="source-search-form" onSubmit={handleSearchSubmit}>
          <label className="source-search-query"><span>What are you looking for?</span><input aria-label="Search repository source" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} maxLength={500} minLength={2} placeholder="e.g. How is JWT authentication validated?" disabled={selectedRepository.indexing_status !== "indexed"} /></label>
          <label className="source-search-mode"><span>Retrieval mode</span><select aria-label="Retrieval mode" value={searchMode} onChange={(event) => setSearchMode(event.target.value)}><option value="hybrid">Hybrid (recommended)</option><option value="semantic">Semantic</option><option value="keyword">Keyword</option></select></label>
          <button className="button button-primary source-search-submit" type="submit" disabled={searchLoading || searchQuery.trim().length < 2 || selectedRepository.indexing_status !== "indexed" || (searchMode !== "keyword" && selectedRepository.embedding_status !== "embedded")}>
            {searchLoading ? <><LoaderCircle className="spin" size={15} /> Searching…</> : <><Search size={15} /> Search sources</>}
          </button>
        </form>
        {selectedRepository.indexing_status !== "indexed" && <p className="source-search-hint">Index this repository's source files before searching.</p>}
        {selectedRepository.indexing_status === "indexed" && searchMode !== "keyword" && selectedRepository.embedding_status !== "embedded" && <p className="source-search-hint">Generate embeddings to enable semantic and hybrid retrieval. Keyword search works independently.</p>}
        {searchError && <p className="field-error indexing-error" role="alert"><AlertCircle size={14} />{searchError}</p>}
        {searchPayload && <div className="source-search-results" aria-live="polite">
          <div className="source-search-results-heading"><div><strong>{searchPayload.result_count} source matches</strong><span>{searchPayload.repository} · commit {searchPayload.commit_sha.slice(0, 7)}</span></div><button className="button button-quiet button-small" type="button" onClick={() => setSearchPayload(null)}>Clear results</button></div>
          {searchPayload.results.length === 0 ? <div className="source-search-empty"><Search size={18} /><span>No matching source chunks found. Try a different phrase or switch retrieval mode.</span></div> : <div className="source-search-result-list">
            {searchPayload.results.map((item, resultIndex) => <article className="source-search-result" key={item.chunk_id}>
              <div className="source-search-result-top"><span className="source-search-result-rank">{String(resultIndex + 1).padStart(2, "0")}</span><div className="source-search-result-path"><FileCode2 size={14} /><strong>{item.file_path}</strong><span>Lines {item.start_line}–{item.end_line}</span></div><span className="source-search-result-score">{Math.round(item.score * 100)}%</span></div>
              {item.symbol_names.length > 0 && <div className="source-search-symbols">{item.symbol_names.slice(0, 5).map((symbol) => <code key={symbol}>{symbol}</code>)}</div>}
              <pre className="source-search-snippet"><code>{item.snippet}</code></pre>
              <div className="source-search-result-foot"><div className="source-search-match-tags">{item.match_types.map((type) => <span key={type}>{type}</span>)}</div><a href={item.citation_url} target="_blank" rel="noopener noreferrer">Open cited lines <ArrowUpRight size={13} /></a></div>
            </article>)}
          </div>}
        </div>}
      </section>

      <RepositoryChatPanel repository={selectedRepository} />

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
            <div className="file-browser-foot">{entries.length} item{entries.length === 1 ? "" : "s"} · Open source files on GitHub to inspect their full contents</div>
          </>
        )}
      </div>
    </section>
  );
}
