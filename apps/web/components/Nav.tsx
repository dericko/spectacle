"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface NavProps {
  crumb?: { label: string };
}

export function Nav({ crumb }: NavProps) {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = localStorage.getItem("theme") as "light" | "dark" | null;
    setTheme(stored ?? "light");
  }, []);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  }

  return (
    <nav className="nav">
      <div className="nav-inner">
        <Link href="/" className="logo">
          <span className="logo-mark">▶</span>
          Spectacle
        </Link>
        {crumb && (
          <>
            <span className="nav-sep">/</span>
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {crumb.label}
            </span>
          </>
        )}
        <div className="nav-spacer" />
        <Link href="/library" className="btn btn-ghost">Library</Link>
        <button className="btn btn-ghost" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "light" ? "Dark" : "Light"}
        </button>
      </div>
    </nav>
  );
}
