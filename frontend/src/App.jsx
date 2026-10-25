import { useEffect, useState } from "react";
import { BrowserRouter, useLocation, useNavigate } from "react-router-dom";
import { Code2, LoaderCircle } from "lucide-react";
import {
  clearAccessToken,
  getAccessToken,
  getApiHealth,
  getCurrentUser,
  getSavedRepositories,
  saveRepository,
  deleteSavedRepository,
} from "./lib/api.js";
import AuthPage from "./pages/AuthPage.jsx";
import WorkspaceLayout from "./components/layout/WorkspaceLayout.jsx";
import ConnectRepositoryDialog from "./components/repositories/ConnectRepositoryDialog.jsx";
import AppRoutes from "./routes/AppRoutes.jsx";
import { pageDetails } from "./config/pages.js";

function AppController() {
  const location = useLocation();
  const routerNavigate = useNavigate();
  const [theme, setTheme] = useState(() => {
    try {
      return window.localStorage.getItem("repolens-theme") === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return window.localStorage.getItem("repolens-sidebar-collapsed") === "true"; } catch { return false; }
  });
  const [repositories, setRepositories] = useState([]);
  const [selectedRepositoryKey, setSelectedRepositoryKey] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [authStatus, setAuthStatus] = useState("checking");
  const [authMessage, setAuthMessage] = useState("");
  const [apiStatus, setApiStatus] = useState("checking");
  const [connectOpen, setConnectOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [pendingPrompt, setPendingPrompt] = useState("");

  const activeNav = location.pathname.split("/").filter(Boolean)[0] || "overview";
  const pageTitle = pageDetails[activeNav]?.[0] || "Workspace";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle("dark", theme === "dark");
    const themeColor = document.querySelector('meta[name="theme-color"]');
    themeColor?.setAttribute("content", theme === "dark" ? "#0a0d16" : "#f4f6fb");
    try { window.localStorage.setItem("repolens-theme", theme); } catch { /* Session-only theme is still applied. */ }
  }, [theme]);

  useEffect(() => {
    try { window.localStorage.setItem("repolens-sidebar-collapsed", String(sidebarCollapsed)); } catch { /* Optional preference. */ }
  }, [sidebarCollapsed]);

  useEffect(() => {
    let mounted = true;
    getApiHealth().then((payload) => {
      if (mounted) setApiStatus(payload.status === "ok" ? "connected" : "offline");
    }).catch(() => {
      if (mounted) setApiStatus("offline");
    });

    if (!getAccessToken()) {
      setAuthStatus("signed-out");
    } else {
      Promise.all([getCurrentUser(), getSavedRepositories()]).then(([user, savedRepositories]) => {
        if (!mounted) return;
        setCurrentUser(user);
        setRepositories(Array.isArray(savedRepositories) ? savedRepositories : savedRepositories?.items || []);
        const items = Array.isArray(savedRepositories) ? savedRepositories : savedRepositories?.items || [];
        setSelectedRepositoryKey(items[0]?.full_name || "");
        setAuthStatus("authenticated");
      }).catch((requestError) => {
        if (!mounted) return;
        clearAccessToken();
        setRepositories([]);
        setCurrentUser(null);
        setAuthMessage(requestError?.message || "Please sign in to continue.");
        setAuthStatus("signed-out");
      });
    }
    return () => { mounted = false; };
  }, []);

  function toggleTheme() {
    setTheme((current) => current === "dark" ? "light" : "dark");
  }

  async function handleAuthenticated(session) {
    setCurrentUser(session.user);
    setAuthStatus("authenticated");
    setAuthMessage("");
    routerNavigate("/overview", { replace: true });
    try {
      const saved = await getSavedRepositories();
      const items = Array.isArray(saved) ? saved : saved?.items || [];
      setRepositories(items);
      setSelectedRepositoryKey(items[0]?.full_name || "");
    } catch (requestError) {
      setNotice(requestError?.message || "Signed in, but repositories could not be loaded.");
    }
  }

  async function connectRepository(repositoryUrl) {
    const saved = await saveRepository(repositoryUrl);
    setRepositories((current) => {
      const existingIndex = current.findIndex((repository) => repository.id === saved.id || repository.full_name.toLowerCase() === saved.full_name.toLowerCase());
      if (existingIndex < 0) return [...current, saved];
      return current.map((repository, index) => index === existingIndex ? saved : repository);
    });
    setSelectedRepositoryKey(saved.full_name);
    routerNavigate("/explorer");
    return saved;
  }

  async function removeRepository(repositoryId) {
    try {
      await deleteSavedRepository(repositoryId);
      const remaining = repositories.filter((repository) => repository.id !== repositoryId);
      setRepositories(remaining);
      if (!remaining.some((repository) => repository.full_name === selectedRepositoryKey)) setSelectedRepositoryKey(remaining[0]?.full_name || "");
      if (activeNav === "explorer" || activeNav === "conversations") routerNavigate("/repositories");
      setNotice("Repository removed from your workspace.");
    } catch (requestError) {
      setNotice(requestError?.message || "Unable to remove this repository.");
    }
  }

  function updateRepository(updatedRepository) {
    setRepositories((current) => current.map((repository) => repository.id === updatedRepository.id ? updatedRepository : repository));
    setSelectedRepositoryKey(updatedRepository.full_name);
  }

  function signOut() {
    clearAccessToken();
    setCurrentUser(null);
    setRepositories([]);
    setSelectedRepositoryKey("");
    setAuthMessage("");
    setAuthStatus("signed-out");
    setNotice("");
    setPendingPrompt("");
    routerNavigate("/overview", { replace: true });
  }

  function navigate(next, repositoryKey) {
    if (next === "help") {
      setNotice("For API issues, confirm the backend is running and check the response message. Never share .env contents or API keys.");
      routerNavigate("/settings");
      return;
    }
    if (repositoryKey) setSelectedRepositoryKey(repositoryKey);
    setMobileOpen(false);
    routerNavigate("/" + (pageDetails[next] ? next : "overview"));
  }

  function handlePrompt(prompt) {
    if (!repositories.length) {
      setNotice("Connect a repository first, then index its source before asking questions.");
      setConnectOpen(true);
      return;
    }
    const preferred = repositories.find((repository) => repository.indexing_status === "indexed") || repositories[0];
    setSelectedRepositoryKey(preferred.full_name);
    setPendingPrompt(prompt);
    navigate("conversations", preferred.full_name);
  }

  if (authStatus === "checking") {
    return <main className="auth-loading"><span className="auth-brand-mark"><Code2 size={22} /></span><LoaderCircle className="spin" size={20} /><p>Loading your RepoLens workspace…</p></main>;
  }

  if (authStatus !== "authenticated") {
    return <AuthPage initialMessage={authMessage} onAuthenticated={handleAuthenticated} theme={theme} onToggleTheme={toggleTheme} />;
  }

  return (
    <>
      <WorkspaceLayout
        active={activeNav}
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={navigate}
        onConnect={() => setConnectOpen(true)}
        onSignOut={signOut}
        onHelp={() => navigate("help")}
        currentUser={currentUser}
        apiStatus={apiStatus}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
        mobileOpen={mobileOpen}
        onOpenMobile={() => setMobileOpen(true)}
        onCloseMobile={() => setMobileOpen(false)}
      >
        <AppRoutes
          apiStatus={apiStatus}
          repositories={repositories}
          selectedRepositoryKey={selectedRepositoryKey}
          onSelectRepository={setSelectedRepositoryKey}
          onConnect={() => setConnectOpen(true)}
          onPrompt={handlePrompt}
          onNavigate={navigate}
          onBrowseRepository={(repositoryKey) => navigate("explorer", repositoryKey)}
          onRepositoryUpdated={updateRepository}
          onRemoveRepository={removeRepository}
          theme={theme}
          onToggleTheme={toggleTheme}
          currentUser={currentUser}
          onSignOut={signOut}
          onHelp={() => navigate("help")}
          initialPrompt={pendingPrompt}
          onInitialPromptConsumed={() => setPendingPrompt("")}
        />
      </WorkspaceLayout>
      {notice && <div className="toast" role="status" aria-live="polite"><div className="toast-icon"><span>✓</span></div><p>{notice}</p><button className="icon-button toast-close" type="button" onClick={() => setNotice("")} aria-label="Dismiss notification">×</button></div>}
      {connectOpen && <ConnectRepositoryDialog onClose={() => setConnectOpen(false)} onNotice={setNotice} onConnectRepository={connectRepository} />}
    </>
  );
}

export default function App() {
  return <BrowserRouter><AppController /></BrowserRouter>;
}
