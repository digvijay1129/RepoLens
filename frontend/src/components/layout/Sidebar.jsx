import { ArrowRight, ArrowUpRight, ChevronDown, Code2, Github, LayoutDashboard, LifeBuoy, MessageSquareText, Settings2, Sparkles, X } from "lucide-react";
import BrandMark from "../common/BrandMark.jsx";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "repositories", label: "Repositories", icon: Github },
  { id: "explorer", label: "Code explorer", icon: Code2 },
  { id: "conversations", label: "AI chat", icon: MessageSquareText },
];

export default function Sidebar({ active, onNavigate, onConnect, mobileOpen, onClose, currentUser, collapsed = false }) {
  return (
    <>
      {mobileOpen && <button className="mobile-scrim" type="button" aria-label="Close menu" onClick={onClose} />}
      <aside className={"sidebar" + (mobileOpen ? " sidebar--open" : "") + (collapsed ? " sidebar--collapsed" : "")}>
        <div className="sidebar-brand">
          <BrandMark /><div className="brand-wordmark">repo<span>lens</span><sup>β</sup></div>
          <button className="icon-button sidebar-close" type="button" onClick={onClose} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <button className="workspace-switcher" type="button" onClick={() => onNavigate("overview")} title="Go to workspace overview"><div className="workspace-avatar">R</div><div className="workspace-copy"><span className="workspace-label">WORKSPACE</span><strong>My workspace</strong></div><ChevronDown size={15} className="workspace-chevron" /></button>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} title={collapsed ? item.label : undefined} className={"nav-item" + (active === item.id ? " nav-item--active" : "")} type="button" onClick={() => { onNavigate(item.id); onClose(); }}>
              <Icon size={18} strokeWidth={1.8} /><span className="nav-item-label">{item.label}</span>
              {active === item.id && <i className="nav-active-mark" />}
            </button>;
          })}
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-section-label">PERSONAL</div>
        <nav className="primary-nav" aria-label="Personal navigation">
          <button title={collapsed ? "Settings" : undefined} className={"nav-item" + (active === "settings" ? " nav-item--active" : "")} type="button" onClick={() => { onNavigate("settings"); onClose(); }}><Settings2 size={18} strokeWidth={1.8} /><span className="nav-item-label">Settings</span></button>
          <button title={collapsed ? "Help & support" : undefined} className="nav-item" type="button" onClick={() => onNavigate("help")}><LifeBuoy size={18} strokeWidth={1.8} /><span className="nav-item-label">Help & support</span><ArrowUpRight size={14} className="nav-external" /></button>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-plan-card"><div className="plan-icon"><Sparkles size={17} /></div><strong>Your code, understood.</strong><p>Source-grounded insights for your next engineering task.</p><button type="button" className="plan-link" onClick={onConnect}>Add a repository <ArrowRight size={14} /></button></div>
          <div className="profile-row"><div className="profile-avatar">{(currentUser?.display_name || currentUser?.email || "D").slice(0, 1).toUpperCase()}</div><div className="profile-info"><strong>{currentUser?.display_name || "Developer"}</strong><span>{currentUser?.email || "Authenticated workspace"}</span></div><span className="profile-auth-dot" aria-label="Signed in" /></div>
        </div>
      </aside>
    </>
  );
}
