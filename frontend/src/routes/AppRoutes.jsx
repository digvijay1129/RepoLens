import { Navigate, Route, Routes } from "react-router-dom";
import OverviewPage from "../pages/OverviewPage.jsx";
import RepositoriesPage from "../pages/RepositoriesPage.jsx";
import CodeExplorerPage from "../pages/CodeExplorerPage.jsx";
import ConversationsPage from "../pages/ConversationsPage.jsx";
import SettingsPage from "../pages/SettingsPage.jsx";

export default function AppRoutes({
  apiStatus,
  repositories,
  selectedRepositoryKey,
  onSelectRepository,
  onConnect,
  onPrompt,
  onNavigate,
  onBrowseRepository,
  onRepositoryUpdated,
  onRemoveRepository,
  theme,
  onToggleTheme,
  currentUser,
  onSignOut,
  onHelp,
  initialPrompt,
  onInitialPromptConsumed,
}) {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="/overview" element={
        <OverviewPage
          apiStatus={apiStatus}
          repositories={repositories}
          onConnect={onConnect}
          onPrompt={onPrompt}
          onNavigate={onNavigate}
          onBrowseRepository={onBrowseRepository}
        />
      } />
      <Route path="/repositories" element={
        <RepositoriesPage repositories={repositories} onConnect={onConnect} onBrowse={onBrowseRepository} onRemove={onRemoveRepository} />
      } />
      <Route path="/explorer" element={
        <CodeExplorerPage
          key={selectedRepositoryKey || "no-selected-repository"}
          repositories={repositories}
          selectedRepositoryKey={selectedRepositoryKey}
          onSelectRepository={onSelectRepository}
          onConnect={onConnect}
          onRepositoryUpdated={onRepositoryUpdated}
        />
      } />
      <Route path="/conversations" element={
        <ConversationsPage
          repositories={repositories}
          selectedRepositoryKey={selectedRepositoryKey}
          onSelectRepository={onSelectRepository}
          onConnect={onConnect}
          onGoToExplorer={() => onNavigate("explorer", selectedRepositoryKey)}
          initialPrompt={initialPrompt}
          onInitialPromptConsumed={onInitialPromptConsumed}
        />
      } />
      <Route path="/settings" element={
        <SettingsPage theme={theme} onToggleTheme={onToggleTheme} currentUser={currentUser} apiStatus={apiStatus} onSignOut={onSignOut} onHelp={onHelp} />
      } />
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}
