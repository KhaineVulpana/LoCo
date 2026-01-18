import React from "react";
import { NavLink } from "react-router-dom";

const navItems = [
  { path: "/", label: "Chat" },
  { path: "/history", label: "History" },
  { path: "/knowledge", label: "Knowledge" },
  { path: "/agents", label: "Agents" },
  { path: "/builder", label: "Agent Builder" },
  { path: "/settings", label: "Settings" }
];

const SideNav: React.FC = () => {
  return (
    <aside className="sidenav">
      <div className="brand">
        <span className="brand-mark">LoCo</span>
        <span className="brand-sub">Agent Studio</span>
      </div>
      <nav className="nav-links">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              isActive ? "nav-link nav-link-active" : "nav-link"
            }
            end={item.path === "/"}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidenav-footer">
        <span className="muted">LoCo Agent Suite</span>
        <span className="muted">Local-first, LAN-ready</span>
      </div>
    </aside>
  );
};

export default SideNav;
