"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/objects/Lead/", match: "/objects/", label: "Objects" },
  { href: "/fields/", match: "/fields/", label: "Fields" },
  { href: "/journeys/", match: "/journeys/", label: "Journeys" },
  { href: "/queries/", match: "/queries/", label: "Queries" },
  { href: "/calculated-insights/", match: "/calculated-insights/", label: "Calculated insights" },
  { href: "/data-cloud/", match: "/data-cloud/", label: "Data Cloud" },
  { href: "/changes/", match: "/changes/", label: "Changes" },
];

export function NavLinks() {
  const p = usePathname() || "/";
  return (
    <nav className="flex flex-wrap items-center gap-x-5 gap-y-1 order-last sm:order-none w-full sm:w-auto" aria-label="Primary">
      {links.map((l) => (
        <Link key={l.href} href={l.href} className="nav-link" aria-current={p.startsWith(l.match) ? "page" : undefined}>{l.label}</Link>
      ))}
    </nav>
  );
}
