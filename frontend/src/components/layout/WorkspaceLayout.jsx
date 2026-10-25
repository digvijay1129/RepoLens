import { ChevronRight, CircleHelp, LogOut, Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Sidebar from "./Sidebar.jsx";
import ThemeToggle from "../common/ThemeToggle.jsx";

const pageTitles = {
  overview: "Overview",
  repositories: "Repositories",
  explorer: "Code explorer",
  conversations: "AI chat",
  settings: "Settings",
};

export default function WorkspaceLayout({
  active,
  theme,
  onToggleTheme,
  onNavigate,
  onConnect,
  onSignOut,
  onHelp,
  currentUser,
  apiStatus,
  collapsed,
  onToggleCollapsed,
  mobileOpen,
  onOpenMobile,
  onCloseMobile,
  children,
}) {
  const pageTitle = pageTitles[active] || "Workspace";
  return (
    <div className={`app-shell ${collapsed ? "app-shell--sidebar-collapsed" : ""}`}>
      <Sidebar
        active={active}
        onNavigate={onNavigate}
        onConnect={onConnect}
        mobileOpen={mobileOpen}
        onClose={onCloseMobile}
        currentUser={currentUser}
        collapsed={collapsed}
      />
      <main className={`main-shell ${collapsed ? "main-shell--collapsed" : ""}`}>
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu-button" type="button" onClick={onOpenMobile} aria-label="Open navigation">
              <Menu size={20} />
            </button>
            <button className="icon-button desktop-sidebar-toggle" type="button" onClick={onToggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
              {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
            <div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} className="breadcrumb-slash" /><strong>{pageTitle}</strong></div>
          </div>
          <div className="topbar-actions">
            <div className="environment-pill"><span /> WORKSPACE</div>
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            <button className="icon-button topbar-help" type="button" onClick={onHelp} aria-label="Help and support" title="Help and support"><CircleHelp size={18} /></button>
            <span className="current-user-email" title={currentUser?.email}>{currentUser?.email}</span>
            <div className="topbar-divider" />
            <button className="icon-button sign-out-button" type="button" onClick={onSignOut} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>
          </div>
        </header>
        <div className="page-content">{children}
          <footer className="app-footer">
            <span>© 2026 RepoLens <i className="footer-separator">·</i> Codebase intelligence</span>
            <span><i className="footer-health-dot" />{apiStatus === "connected" ? "API connected" : apiStatus === "checking" ? "Checking backend" : "Backend unavailable"}</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
