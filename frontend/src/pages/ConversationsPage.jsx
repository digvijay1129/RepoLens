import { useEffect, useState } from "react";
import { ArrowRight, Bot, GitBranch, MessageSquareText, Plus } from "lucide-react";
import RepositoryChatPanel from "../components/chat/RepositoryChatPanel.jsx";

export default function ConversationsPage({
  repositories,
  selectedRepositoryKey,
  onSelectRepository,
  onConnect,
  onGoToExplorer,
  initialPrompt,
  onInitialPromptConsumed,
}) {
  const selectedRepository = repositories.find((item) => item.full_name === selectedRepositoryKey) || repositories[0] || null;
  const [sidePrompt, setSidePrompt] = useState("");

  useEffect(() => {
    if (!selectedRepository && repositories.length > 0) onSelectRepository(repositories[0].full_name);
  }, [selectedRepository, repositories, onSelectRepository]);

  if (!selectedRepository) {
    return (
      <section className="conversation-page conversation-page-empty animate-fade-in">
        <div className="conversation-empty-mark"><Bot size={27} /></div>
        <span className="eyebrow">REPOLENS AI</span>
        <h1>Chat with your codebase</h1>
        <p>Connect a public GitHub repository, index its source code, and ask questions grounded in real files and line-level citations.</p>
        <button className="button button-primary" type="button" onClick={onConnect}><Plus size={16} /> Connect repository</button>
      </section>
    );
  }

  return (
    <section className="conversation-page animate-fade-in">
      <div className="conversation-page-heading">
        <div>
          <span className="eyebrow"><span className="eyebrow-line" /> SOURCE-GROUNDED ASSISTANT</span>
          <h1>Ask your codebase</h1>
          <p>Explore architecture, trace a flow, or understand a function with verifiable source references.</p>
        </div>
        <div className="conversation-context">
          <span className="conversation-context-icon"><GitBranch size={16} /></span>
          <label htmlFor="chat-repository-select">Repository</label>
          <select id="chat-repository-select" aria-label="Select chat repository" value={selectedRepository.full_name} onChange={(event) => onSelectRepository(event.target.value)}>
            {repositories.map((repository) => <option key={repository.id} value={repository.full_name}>{repository.full_name}</option>)}
          </select>
          <button className="button button-secondary button-small" type="button" onClick={onGoToExplorer}>Open explorer <ArrowRight size={14} /></button>
        </div>
      </div>
      <div className="conversation-chat-layout">
        <RepositoryChatPanel key={selectedRepository.id} repository={selectedRepository} initialPrompt={initialPrompt || sidePrompt} onInitialPromptConsumed={() => { setSidePrompt(""); onInitialPromptConsumed?.(); }} />
        <aside className="conversation-side-notes panel">
          <div className="conversation-side-icon"><MessageSquareText size={18} /></div>
          <h2>Ask with context</h2>
          <p>RepoLens retrieves relevant source chunks before asking the model to answer.</p>
          <div className="conversation-suggestion-list">
            {["How does authentication work?", "Where is the database configured?", "Trace the request lifecycle."].map((prompt) => (
              <button key={prompt} type="button" onClick={() => setSidePrompt(prompt)}>{prompt}<ArrowRight size={13} /></button>
            ))}
          </div>
          <div className="conversation-citation-note"><span /> Answers can include file paths, line ranges, and source links.</div>
        </aside>
      </div>
    </section>
  );
}
