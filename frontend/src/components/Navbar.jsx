import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";

export default function Navbar() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "light");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("smr-theme", theme); } catch { /* private mode */ }
  }, [theme]);

  return (
    <header className="nav">
      <Link to="/" className="brand" aria-label="Social Media Repurposer home">
        <span className="brand-mark" aria-hidden="true">⚡</span>
        <span>repurposer</span>
      </Link>
      <nav className="nav-links">
        <NavLink to="/" end>Create</NavLink>
        <NavLink to="/dashboard">My projects</NavLink>
        <button
          className="btn small ghost"
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
        >
          {theme === "light" ? "🌙 Dark" : "☀️ Light"}
        </button>
      </nav>
    </header>
  );
}
