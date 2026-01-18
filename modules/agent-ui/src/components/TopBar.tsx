import React from "react";
import { NavLink } from "react-router-dom";
import { useAppContext } from "../lib/appContext";
import { NAV_ITEMS } from "../lib/navItems";
import Select from "./Select";

const TopBar: React.FC = () => {
  const { settings, updateSettings, workspaces } = useAppContext();

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="brand-inline">
          <span className="brand-mark">LoCo</span>
          <span className="brand-sub">Agent Studio</span>
        </div>
        <nav className="topbar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                isActive ? "topbar-link topbar-link-active" : "topbar-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="topbar-right">
        <div className="connection">
          <span className="status-dot" />
          <span className="connection-text">{settings.serverUrl}</span>
        </div>
        <Select
          aria-label="Workspace"
          value={settings.workspaceId ?? ""}
          onChange={(event) => updateSettings({ workspaceId: event.target.value })}
        >
          <option value="" disabled>
            Workspace
          </option>
          {workspaces.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name}
            </option>
          ))}
        </Select>
      </div>
    </header>
  );
};

export default TopBar;
