import Link from "next/link";
import { fieldHref, fieldsByKey, objectLabel } from "@/lib/data";

export function Chip({ children, tone = "line", className = "" }: { children: React.ReactNode; tone?: "line" | "fill" | "accent" | "accent2"; className?: string }) {
  const cls = tone === "fill" ? "chip chip-fill" : tone === "accent" ? "chip chip-accent" : tone === "accent2" ? "chip chip-accent2" : "chip";
  return <span className={`${cls} ${className}`}>{children}</span>;
}

export function Section({ title, eyebrow, children, aside, id }: { title: string; eyebrow?: string; children: React.ReactNode; aside?: React.ReactNode; id?: string }) {
  return (
    <section id={id} className="mt-10 first:mt-0">
      <div className="flex items-end justify-between gap-4 mb-3">
        <div>
          {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
          <h2 className="text-xl font-medium tracking-tight">{title}</h2>
        </div>
        {aside}
      </div>
      <div className="rule mb-4" />
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="card p-4">
      <div className="eyebrow">{label}</div>
      <div className="text-3xl font-light tracking-tight mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-xs text-ink-3 mt-1">{hint}</div>}
    </div>
  );
}

export function FieldLink({ k, showObject = true }: { k: string; showObject?: boolean }) {
  const f = fieldsByKey.get(k);
  if (!f) return <span className="mono text-ink-3">{k}</span>;
  return (
    <Link href={fieldHref(k)} className="hover:underline decoration-[var(--accent)]">
      {showObject && <span className="text-ink-3">{objectLabel(f.object)} · </span>}
      <span className="mono">{f.apiName}</span>
    </Link>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-ink-3 italic">{children}</p>;
}

export function Breadcrumbs({ items }: { items: { href?: string; label: string }[] }) {
  return (
    <nav className="text-xs text-ink-3 mb-4 flex flex-wrap items-center gap-1" aria-label="Breadcrumb">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span aria-hidden>/</span>}
          {it.href ? <Link href={it.href} className="hover:text-ink">{it.label}</Link> : <span className="text-ink-2">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function StatusDot({ status }: { status?: string | null }) {
  const s = (status || "").toUpperCase();
  const color = ["ACTIVE", "SUCCESS", "PUBLISHED", "READY", "RUNNING"].includes(s) ? "var(--seafoam)" : ["FAILED", "ERROR", "STOPPED", "FAILURE"].includes(s) ? "var(--accent)" : "var(--horizon)";
  return <span className="inline-flex items-center gap-1.5 text-xs text-ink-2"><span className="dot" style={{ background: color, outline: "1px solid var(--line-strong)" }} />{status || "—"}</span>;
}

export function Qiwi({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 200" className={className} aria-hidden>
      <rect x="20" y="10" width="80" height="150" rx="40" className="qiwi" />
      <rect x="34" y="28" width="52" height="114" rx="26" className="qiwi" style={{ opacity: 0.55 }} />
      <path d="M85 150 L112 190" className="qiwi" />
      <path d="M48 28 L48 142" className="qiwi" style={{ opacity: 0.35 }} />
      <path d="M20 85 L100 85" className="qiwi" style={{ opacity: 0.35 }} />
    </svg>
  );
}
