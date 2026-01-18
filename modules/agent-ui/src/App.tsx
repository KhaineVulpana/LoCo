import React, { useEffect } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import TopBar from "./components/TopBar";
import { AppProvider, useAppContext } from "./lib/appContext";
import ChatPage from "./pages/ChatPage";
import HistoryPage from "./pages/HistoryPage";
import TracePage from "./pages/TracePage";
import KnowledgePage from "./pages/KnowledgePage";
import AgentsPage from "./pages/AgentsPage";
import BuilderPage from "./pages/BuilderPage";
import SettingsPage from "./pages/SettingsPage";

const AppShell: React.FC = () => {
  const { refreshWorkspaces, refreshFolders, refreshAgents, settings } = useAppContext();
  const location = useLocation();
  const showTopBar = location.pathname !== "/";

  useEffect(() => {
    refreshWorkspaces();
  }, [refreshWorkspaces]);

  useEffect(() => {
    if (settings.workspaceId) {
      refreshFolders(settings.workspaceId);
      refreshAgents(settings.workspaceId);
    }
  }, [settings.workspaceId, refreshFolders, refreshAgents]);

  return (
    <div className="app-shell">
      {showTopBar ? <TopBar /> : null}
      <main className="page">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/trace" element={<TracePage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/builder" element={<BuilderPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
};

export default App;
