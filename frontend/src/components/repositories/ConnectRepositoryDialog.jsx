import { AlertCircle, ArrowRight, Github, LoaderCircle, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { normalizeGitHubRepositoryUrl } from "../../lib/githubRepository.js";

export default function ConnectRepositoryDialog({ onClose, onNotice, onConnectRepository }) {
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
