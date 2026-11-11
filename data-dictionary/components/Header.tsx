import Link from "next/link";
import { Search } from "./Search";
import { ThemeToggle } from "./ThemeToggle";
import { NavLinks } from "./NavLinks";

export function Header() {
  return (
    <header className="sticky top-0 z-20 bg-[var(--bg)]/90 backdrop-blur border-b border-[var(--line)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Link href="/" className="flex items-center gap-3 shrink-0" aria-label="Quanata Data Dictionary home">
          {/* eslint-disable-next-line @next/next/no-img-element -- static SVG logo, no optimization needed */}
          <img src="/brand/quanata-carbon.svg" alt="Quanata" className="h-5 w-auto dark-hide" />
          {/* eslint-disable-next-line @next/next/no-img-element -- static SVG logo, no optimization needed */}
          <img src="/brand/quanata-white.svg" alt="" className="h-5 w-auto dark-show" aria-hidden />
          <span className="hidden sm:inline text-sm text-ink-3 border-l border-[var(--line-strong)] pl-3">Data Dictionary</span>
        </Link>
        <NavLinks />
        <div className="ml-auto flex items-center gap-3 w-full sm:w-auto">
          <Search />
          <ThemeToggle />
        </div>
      </div>
      <style>{`.dark-show{display:none}:root[data-theme="dark"] .dark-hide{display:none}:root[data-theme="dark"] .dark-show{display:inline}@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .dark-hide{display:none}:root:not([data-theme="light"]) .dark-show{display:inline}}`}</style>
    </header>
  );
}
