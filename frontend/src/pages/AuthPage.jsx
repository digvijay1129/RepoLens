import { AlertCircle, ArrowRight, Code2, GitBranch, Github, LoaderCircle, LockKeyhole, LogIn, Mail, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";
import { setAccessToken, loginAccount, registerAccount } from "../lib/api.js";
import ThemeToggle from "../components/common/ThemeToggle.jsx";

export default function AuthPage({ onAuthenticated, initialMessage = "", theme, onToggleTheme }) {
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
      <ThemeToggle theme={theme} onToggle={onToggleTheme} className="auth-theme-toggle" />
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
          <div className="auth-card-foot"><ShieldCheck size={15} /><span>Private account session · Public repository support</span></div>
        </section>
      </div>
      <footer className="auth-footer"><span>© 2026 RepoLens</span><span><i /> Built for developers, with source-first principles</span></footer>
    </main>
  );
}
