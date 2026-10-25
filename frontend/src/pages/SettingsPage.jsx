import { Check, CircleHelp, LogOut, Moon, Sun, UserRound, Wifi } from "lucide-react";
import ThemeToggle from "../components/common/ThemeToggle.jsx";

export default function SettingsPage({ theme, onToggleTheme, currentUser, apiStatus, onSignOut, onHelp }) {
  return (
    <section className="settings-page animate-fade-in">
      <div className="settings-page-heading">
        <span className="eyebrow"><span className="eyebrow-line" /> PREFERENCES</span>
        <h1>Workspace settings</h1>
        <p>Manage your display preference, account session, and connection status.</p>
      </div>
      <div className="settings-grid">
        <article className="settings-card panel">
          <div className="settings-card-heading"><span className="settings-card-icon"><Sun size={18} /></span><div><h2>Appearance</h2><p>Choose how RepoLens looks on this device.</p></div></div>
          <div className="appearance-options">
            <button type="button" className={`appearance-option ${theme === "dark" ? "is-selected" : ""}`} onClick={() => theme !== "dark" && onToggleTheme()} aria-pressed={theme === "dark"}>
              <span className="appearance-preview appearance-preview-dark"><i /><i /><i /><b /></span><span><Moon size={15} /> Dark</span>{theme === "dark" && <Check size={16} />}
            </button>
            <button type="button" className={`appearance-option ${theme === "light" ? "is-selected" : ""}`} onClick={() => theme !== "light" && onToggleTheme()} aria-pressed={theme === "light"}>
              <span className="appearance-preview appearance-preview-light"><i /><i /><i /><b /></span><span><Sun size={15} /> Light</span>{theme === "light" && <Check size={16} />}
            </button>
          </div>
          <div className="settings-card-foot"><span>Current preference</span><ThemeToggle theme={theme} onToggle={onToggleTheme} /></div>
        </article>
        <article className="settings-card panel">
          <div className="settings-card-heading"><span className="settings-card-icon"><UserRound size={18} /></span><div><h2>Account</h2><p>Session details for this workspace.</p></div></div>
          <div className="settings-detail-row"><span>Signed in as</span><strong>{currentUser?.display_name || "Developer"}</strong></div>
          <div className="settings-detail-row"><span>Email address</span><strong className="settings-email">{currentUser?.email || "Not available"}</strong></div>
          <div className="settings-detail-row"><span>Session</span><strong className="settings-inline-status"><i /> Authenticated</strong></div>
          <button type="button" className="button button-secondary settings-signout" onClick={onSignOut}><LogOut size={15} /> Sign out</button>
        </article>
        <article className="settings-card panel">
          <div className="settings-card-heading"><span className="settings-card-icon"><Wifi size={18} /></span><div><h2>Service health</h2><p>Live status of your local RepoLens backend.</p></div></div>
          <div className={`service-health-state service-health-${apiStatus}`}><span className="service-health-dot" />{apiStatus === "connected" ? "Backend reachable" : apiStatus === "checking" ? "Checking connection" : "Backend unavailable"}</div>
          <p className="settings-muted">API requests are sent to your configured backend URL. Secrets remain on the backend.</p>
          <button type="button" className="button button-secondary settings-help-button" onClick={onHelp}><CircleHelp size={15} /> Troubleshooting help</button>
        </article>
      </div>
    </section>
  );
}
