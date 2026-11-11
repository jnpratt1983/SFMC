"use client";
import { useMemo, useState } from "react";
import Link from "next/link";

export type Row = { key: string; apiName: string; label: string; typeDetail: string; custom: boolean; description: string; definition: string; inSfmc: boolean; inDataCloud: boolean; journeys: number; queries: number; dc: number; object: string; objectLabel: string };

type SortKey = "apiName" | "label" | "typeDetail" | "journeys" | "queries" | "dc";

export function FieldTable({ rows, showObject = false }: { rows: Row[]; showObject?: boolean }) {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [use, setUse] = useState("all");
  const [sort, setSort] = useState<SortKey>("apiName");
  const [dir, setDir] = useState<1 | -1>(1);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    let r = rows;
    if (s) r = r.filter((x) => x.apiName.toLowerCase().includes(s) || x.label.toLowerCase().includes(s) || (x.description || "").toLowerCase().includes(s) || (x.definition || "").toLowerCase().includes(s) || x.typeDetail.toLowerCase().includes(s));
    if (kind === "custom") r = r.filter((x) => x.custom); else if (kind === "standard") r = r.filter((x) => !x.custom);
    if (use === "journeys") r = r.filter((x) => x.journeys > 0);
    else if (use === "queries") r = r.filter((x) => x.queries > 0);
    else if (use === "dc") r = r.filter((x) => x.dc > 0);
    else if (use === "sfmc") r = r.filter((x) => x.inSfmc);
    else if (use === "datacloud") r = r.filter((x) => x.inDataCloud);
    else if (use === "unused") r = r.filter((x) => !x.journeys && !x.queries && !x.dc);
    else if (use === "nosync") r = r.filter((x) => !x.inSfmc && !x.inDataCloud);
    return [...r].sort((a, b) => {
      const av = a[sort], bv = b[sort];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir || a.apiName.localeCompare(b.apiName);
      return String(av).localeCompare(String(bv), undefined, { sensitivity: "base" }) * dir;
    });
  }, [rows, q, kind, use, sort, dir]);

  function th(label: string, k: SortKey, cls = "") {
    const active = sort === k;
    return (
      <th className={`sortable ${cls}`} onClick={() => { if (active) setDir(dir === 1 ? -1 : 1); else { setSort(k); setDir(k === "apiName" || k === "label" || k === "typeDetail" ? 1 : -1); } }} aria-sort={active ? (dir === 1 ? "ascending" : "descending") : "none"}>
        {label}{active ? (dir === 1 ? " ↑" : " ↓") : ""}
      </th>
    );
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-2 mb-3">
        <input className="search sm:max-w-sm" placeholder="Filter by API name, label, definition…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter fields" />
        <select className="search sm:w-44" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Field kind">
          <option value="all">Custom + standard</option><option value="custom">Custom only</option><option value="standard">Standard only</option>
        </select>
        <select className="search sm:w-64" value={use} onChange={(e) => setUse(e.target.value)} aria-label="Usage filter">
          <option value="all">Any usage</option>
          <option value="journeys">Used in a journey</option>
          <option value="queries">Used in a SQL query</option>
          <option value="dc">Used in Data Cloud (CI, segment, …)</option>
          <option value="sfmc">Synced to Marketing Cloud</option>
          <option value="datacloud">Ingested to Data Cloud</option>
          <option value="unused">No usage found</option>
          <option value="nosync">Not synced anywhere</option>
        </select>
        <div className="text-xs text-ink-3 self-center sm:ml-auto tabular-nums">{filtered.length} of {rows.length} fields</div>
      </div>
      <div className="table-wrap card">
        <table className="dd">
          <thead>
            <tr>
              {showObject && <th>Object</th>}
              {th("API name", "apiName")}
              {th("Label", "label")}
              <th className="min-w-[18rem]">Definition</th>
              {th("Type", "typeDetail")}
              <th>Synced</th>
              {th("Journeys", "journeys", "text-right")}
              {th("Queries", "queries", "text-right")}
              {th("Data Cloud", "dc", "text-right")}
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const [o, ...rest] = r.key.split(".");
              return (
                <tr key={r.key}>
                  {showObject && <td className="text-ink-2 whitespace-nowrap">{r.objectLabel}</td>}
                  <td><Link href={`/fields/${o}/${rest.join(".")}/`} className="mono hover:underline decoration-[var(--accent)]">{r.apiName}</Link>{r.custom ? "" : <span className="ml-2 chip" style={{ fontSize: "0.6rem" }}>std</span>}</td>
                  <td className="text-ink-2">{r.label}</td>
                  <td className="text-ink-2 text-xs leading-snug max-w-[28rem]" title={r.definition}>{r.definition ? <span className="line-clamp-2">{r.definition}</span> : <span className="text-ink-3">–</span>}</td>
                  <td className="text-ink-2 whitespace-nowrap">{r.typeDetail}</td>
                  <td className="whitespace-nowrap">
                    {r.inSfmc && <span className="chip chip-fill mr-1" title="Marketing Cloud Connect synced DE">MC</span>}
                    {r.inDataCloud && <span className="chip chip-fill" title="Data Cloud CRM stream">DC</span>}
                  </td>
                  <td className="text-right tabular-nums">{r.journeys || <span className="text-ink-3">–</span>}</td>
                  <td className="text-right tabular-nums">{r.queries || <span className="text-ink-3">–</span>}</td>
                  <td className="text-right tabular-nums">{r.dc || <span className="text-ink-3">–</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && <div className="p-6 text-sm text-ink-3">No fields match.</div>}
      </div>
    </div>
  );
}
