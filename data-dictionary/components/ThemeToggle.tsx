"use client";
import { useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
function read() { try { return localStorage.getItem("qdd-theme") || ""; } catch { return ""; } }
function subscribe(cb: () => void) { listeners.add(cb); return () => { listeners.delete(cb); }; }
function write(next: string) {
  try { if (next) localStorage.setItem("qdd-theme", next); else localStorage.removeItem("qdd-theme"); } catch {}
  if (next) document.documentElement.setAttribute("data-theme", next); else document.documentElement.removeAttribute("data-theme");
  listeners.forEach((l) => l());
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, read, () => "");
  const label = theme === "dark" ? "Dark" : theme === "light" ? "Light" : "Auto";
  return (
    <button onClick={() => write(theme === "dark" ? "light" : theme === "light" ? "" : "dark")} className="chip hover:border-[var(--accent)] hover:text-[var(--accent)]" title="Toggle theme" aria-label={`Theme: ${label}`}>
      <span className="dot" style={{ background: theme === "dark" ? "var(--dust)" : "var(--carbon)" }} />{label}
    </button>
  );
}
