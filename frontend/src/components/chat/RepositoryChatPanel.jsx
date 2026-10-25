import { AlertCircle, ArrowRight, ArrowUpRight, Bot, Check, Copy, FileCode2, LoaderCircle, MessageSquareText, Plus, Sparkles, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { chatWithSavedRepository, getRepositoryConversations, getRepositoryConversation } from "../../lib/api.js";

export default function RepositoryChatPanel({ repository, initialPrompt = "", onInitialPromptConsumed }) {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState(initialPrompt || "");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadingHistoryError, setLoadingHistoryError] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState("");

  useEffect(() => {
    let cancelled = false;
    setConversations([]);
    setConversationId("");
    setMessages([]);
    setDraft("");
    setError("");
    setLoadingHistoryError("");
    if (!repository?.id) return undefined;
    getRepositoryConversations(repository.id).then((result) => {
      if (!cancelled) setConversations(result.items || []);
    }).catch((requestError) => {
      if (!cancelled) setLoadingHistoryError(requestError?.message || "Unable to load saved conversations.");
    });
    return () => { cancelled = true; };
  }, [repository?.id]);

  useEffect(() => {
    if (!initialPrompt) return;
    setDraft(initialPrompt);
    onInitialPromptConsumed?.();
  // The callback is used only when a new prompt arrives; not depending on its identity avoids re-running for inline callbacks.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  async function handleConversationChange(event) {
    const nextId = event.target.value;
    setError("");
    setLoadingHistoryError("");
    if (!nextId) {
      setConversationId("");
      setMessages([]);
      return;
    }
    setHistoryLoading(true);
    try {
      const history = await getRepositoryConversation(repository.id, nextId);
      setConversationId(history.id);
      setMessages(history.messages || []);
    } catch (requestError) {
      setLoadingHistoryError(requestError?.message || "Unable to open this conversation.");
    } finally {
      setHistoryLoading(false);
    }
  }

  function handleNewConversation() {
    setConversationId("");
    setMessages([]);
    setDraft("");
    setError("");
    setLoadingHistoryError("");
  }
  async function handleCopyAnswer(message) {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessageId(message.id);
    } catch {
      setError("Clipboard access is unavailable in this browser. Select and copy the answer text manually.");
    }
  }



  async function handleSubmit(event) {
    event.preventDefault();
    const question = draft.trim();
    if (!repository?.id || repository.indexing_status !== "indexed" || question.length < 2 || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await chatWithSavedRepository(repository.id, {
        message: question,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      });
      setConversationId(response.id);
      setMessages((previous) => [
        ...previous,
        response.user_message,
        response.assistant_message,
      ]);
      setDraft("");
      try {
        const latest = await getRepositoryConversations(repository.id);
        setConversations(latest.items || []);
      } catch {
        // The current answer remains usable if refreshing the history list fails.
      }
    } catch (requestError) {
      setError(requestError?.message || "Unable to answer this question.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rag-chat-panel panel chatgpt-style" aria-labelledby="rag-chat-title">
      <div className="rag-chat-heading">
        <div className="rag-chat-heading-icon"><MessageSquareText size={17} /></div>
        <div className="rag-chat-heading-copy">
          <h2 id="rag-chat-title">Ask RepoLens</h2>
          <p>Answers grounded in retrieved files, with citations you can open and verify.</p>
        </div>
        <span className="rag-chat-provider-pill"><Bot size={12} /> SOURCE-GROUNDED</span>
      </div>
      <div className="rag-chat-toolbar">
        <label className="rag-chat-history-select">
          <span>Conversation history</span>
          <select aria-label="Saved conversations" value={conversationId} onChange={handleConversationChange} disabled={historyLoading || conversations.length === 0}>
            <option value="">New conversation</option>
            {conversations.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
        </label>
        <button className="button button-secondary button-small" type="button" onClick={handleNewConversation} disabled={loading}>
          <Plus size={13} /> New chat
        </button>
      </div>
      {repository.indexing_status !== "indexed" ? (
        <div className="rag-chat-empty">
          <div className="rag-chat-empty-icon"><FileCode2 size={20} /></div>
          <strong>Index this repository first</strong>
          <p>RepoLens needs an indexed source snapshot before it can answer questions about your code.</p>
        </div>
      ) : messages.length === 0 ? (
        <div className="rag-chat-empty">
          <div className="rag-chat-empty-icon"><Sparkles size={20} /></div>
          <strong>What would you like to understand?</strong>
          <p>Ask about architecture, authentication, database setup, or how a request flows through the project.</p>
          <div className="chat-prompt-chips">
            {["How does authentication work?", "Where is the database configured?", "Explain the main request flow"].map((prompt) => (
              <button key={prompt} type="button" onClick={() => setDraft(prompt)}>{prompt}<ArrowRight size={12} /></button>
            ))}
          </div>
          <span>RepoLens uses retrieved source chunks as evidence. If evidence is missing, it should say so.</span>
        </div>
      ) : (
        <div className="rag-chat-messages" aria-live="polite">
          {messages.map((message) => (
            <article className={"rag-chat-message rag-chat-message-" + message.role} key={message.id}>
              <div className="rag-chat-message-avatar">{message.role === "assistant" ? <Bot size={14} /> : <UserRound size={14} />}</div>
              <div className="rag-chat-message-body">
                <div className="rag-chat-message-label">{message.role === "assistant" ? "RepoLens" : "You"}</div>
                <p>{message.content}</p>
                {message.role === "assistant" && (
                  <div className="rag-chat-answer-tools">
                    <button className="rag-chat-copy-answer" type="button" onClick={() => handleCopyAnswer(message)} aria-label={"Copy RepoLens answer " + message.id}>
                      {copiedMessageId === message.id ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy answer</>}
                    </button>
                  </div>
                )}
                {message.role === "assistant" && Array.isArray(message.sources) && message.sources.length > 0 && (
                  <div className="rag-chat-citations">
                    <span className="rag-chat-citations-title">Sources used</span>
                    {message.sources.map((source) => (
                      <a href={source.citation_url} target="_blank" rel="noopener noreferrer" key={source.id}>
                        <span>{source.id}</span><FileCode2 size={12} /><strong>{source.file_path}</strong>
                        <em>L{source.start_line}–L{source.end_line}</em><ArrowUpRight size={12} />
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
          {loading && <div className="rag-chat-thinking"><LoaderCircle className="spin" size={14} /> Retrieving source evidence and preparing an answer…</div>}
        </div>
      )}
      {(error || loadingHistoryError) && <p className="field-error rag-chat-error" role="alert"><AlertCircle size={14} />{error || loadingHistoryError}</p>}
      <form className="rag-chat-composer" onSubmit={handleSubmit}>
        <label htmlFor="rag-chat-message">Your question</label>
        <textarea id="rag-chat-message" aria-label="Ask about this repository" rows={3} maxLength={4000} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about a function, architecture, API, or data flow…" disabled={repository.indexing_status !== "indexed" || loading} />
        <div className="rag-chat-composer-foot">
          <span>Source text is treated as untrusted evidence, not instructions.</span>
          <button className="button button-primary" type="submit" disabled={repository.indexing_status !== "indexed" || draft.trim().length < 2 || loading}>
            {loading ? <><LoaderCircle className="spin" size={14} /> Thinking…</> : <>Ask question <ArrowRight size={14} /></>}
          </button>
        </div>
      </form>
      {historyLoading && <p className="rag-chat-history-loading"><LoaderCircle className="spin" size={13} /> Loading conversation history…</p>}
    </section>
  );
}
