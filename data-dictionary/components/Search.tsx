"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import index from "@/data/search-index.json";

type Row = { t: string; k: string; o?: string; n: string; l: string; ty?: string; j?: number; q?: number; d?: number };
const rows = index as Row[];

function href(r: Row) {
  if (r.t === "field") { const [o, ...rest] = r.k.split("."); return `/fields/${o}/${rest.join(".")}/`; }
  if (r.t === "ci") return `/calculated-insights/${r.k}/`;
  if (r.t === "journey") return `/journeys/${r.k}/`;
  if (r.t === "segment") return `/data-cloud/#segment-${r.k}`;
  return "/";
}
const TYPE_LABEL: Record<string, string> = { field: "Field", ci: "Calculated insight", journey: "Journey", segment: "Segment" };
const OBJ_LABEL: Record<string, string> = { Monthly_Driving_Stat__c: "Monthly Driving Stats", Bill__c: "Bill" };

export function Search({ autoFocus = false, big = false }: { autoFocus?: boolean; big?: boolean }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(0);
  const router = useRouter();
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") { e.preventDefault(); ref.current?.focus(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [] as Row[];
    const terms = s.split(/\s+/);
    const scored = rows.map((r) => {
      const n = r.n.toLowerCase(), l = (r.l || "").toLowerCase(), k = r.k.toLowerCase();
      let score = 0;
      for (const t of terms) {
        if (n === t) score += 100; else if (n.startsWith(t)) score += 40; else if (n.includes(t)) score += 20;
        if (l === t) score += 60; else if (l.startsWith(t)) score += 25; else if (l.includes(t)) score += 12;
        if (k.includes(t)) score += 5;
        if (n.replace(/_/g, "").includes(t.replace(/[_ ]/g, ""))) score += 8;
      }
      if (score && r.t === "field") score += 3;
      return { r, score };
    }).filter((x) => x.score > 0).sort((a, b) => b.score - a.score || a.r.n.localeCompare(b.r.n));
    return scored.slice(0, 12).map((x) => x.r);
  }, [q]);


  return (
    <div className={`relative ${big ? "w-full" : "w-full sm:w-80"}`}>
      <input ref={ref} className={`search ${big ? "text-base py-3" : ""}`} placeholder={big ? "Search a field name, label, calculated insight or journey…" : "Search fields… ( / )"} value={q}
        autoFocus={autoFocus} onChange={(e) => { setQ(e.target.value); setSel(0); setOpen(true); }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, results.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
          else if (e.key === "Enter" && results[sel]) { router.push(href(results[sel])); setOpen(false); }
          else if (e.key === "Escape") { setOpen(false); ref.current?.blur(); }
        }} aria-label="Search" />
      {open && q.trim() && (
        <div className="absolute z-30 mt-1 w-full card shadow-lg overflow-hidden" role="listbox">
          {results.length === 0 && <div className="px-3 py-2 text-sm text-ink-3">No matches</div>}
          {results.map((r, i) => (
            <a key={r.t + r.k} href={href(r)} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onMouseDown={(e) => { e.preventDefault(); router.push(href(r)); setOpen(false); }}
              className={`flex items-center justify-between gap-3 px-3 py-2 text-sm border-b border-[var(--line)] last:border-0 ${i === sel ? "bg-[var(--surface-2)]" : ""}`}>
              <span className="min-w-0">
                <span className="mono block truncate">{r.n}</span>
                <span className="block text-xs text-ink-3 truncate">{r.t === "field" ? `${OBJ_LABEL[r.o || ""] || r.o} · ${r.l} · ${r.ty}` : r.l}</span>
              </span>
              <span className="shrink-0 flex items-center gap-2">
                {r.t === "field" && <span className="text-[0.68rem] text-ink-3 tabular-nums">{r.j} journeys · {r.q} queries · {r.d} DC</span>}
                <span className="chip">{TYPE_LABEL[r.t] || r.t}</span>
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
