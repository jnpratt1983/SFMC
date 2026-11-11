import Link from "next/link";
import { data, fieldsByKey, objectLabel, journeyHref, ciHref, fmtDate, KIND_LABEL } from "@/lib/data";
import { Breadcrumbs, Chip, Empty, Section } from "@/components/ui";

export function generateStaticParams() {
  return data.fields.map((f) => ({ object: f.object, field: f.apiName }));
}
export async function generateMetadata({ params }: { params: Promise<{ object: string; field: string }> }) {
  const { object, field } = await params;
  return { title: `${field} · ${objectLabel(object)}` };
}

const KIND_ORDER = ["entry", "query", "decision", "email", "sms", "push", "salescloud", "contactupdate"];

export default async function FieldPage({ params }: { params: Promise<{ object: string; field: string }> }) {
  const { object, field } = await params;
  const f = fieldsByKey.get(`${object}.${field}`)!;
  const dcCount = f.usage.dc;
  const rows: [string, React.ReactNode][] = [
    ["Label", f.label],
    ["Type", f.typeDetail],
    ["Kind", f.custom ? (f.namespace ? `Custom (package ${f.namespace})` : "Custom") : "Standard"],
    ["Required", f.required ? "Yes" : "No"],
    ["Unique / External Id", `${f.unique ? "Unique" : "Not unique"}${f.externalId ? " · External Id" : ""}`],
    ["Lookup to", f.referenceTo.length ? f.referenceTo.join(", ") : null],
    ["Default", f.defaultValue != null && f.defaultValue !== "" ? String(f.defaultValue) : null],
    ["History tracking", f.historyTracked ? "On" : null],
    ["Created", f.createdDate ? `${fmtDate(f.createdDate)}${f.createdBy ? ` by ${f.createdBy}` : ""}` : null],
    ["Last modified", f.lastModifiedDate ? `${fmtDate(f.lastModifiedDate)}${f.lastModifiedBy ? ` by ${f.lastModifiedBy}` : ""}` : null],
    ["Business status", f.businessStatus],
    ["Business owner", f.businessOwner],
    ["Security classification", f.securityClassification],
    ["Compliance group", f.complianceGroup],
  ];
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { href: `/objects/${f.object}/`, label: objectLabel(f.object) }, { label: f.apiName }]} />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">{objectLabel(f.object)} · {f.custom ? "custom field" : "standard field"}</div>
          <h1 className="h-display text-4xl mt-1 break-all"><span className="mono text-[0.9em] font-normal">{f.apiName}</span></h1>
          <p className="text-ink-2 text-lg mt-1">{f.label}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {f.sfmc.syncedDE ? <Chip tone="fill">Marketing Cloud · {f.sfmc.syncedDE}</Chip> : <Chip>Not synced to Marketing Cloud</Chip>}
          {f.dc.stream ? <Chip tone="fill">Data Cloud · {f.dc.stream}</Chip> : <Chip>Not in Data Cloud</Chip>}
          {f.setupUrl && <a className="chip chip-accent hover:bg-[var(--surface-2)]" href={f.setupUrl} target="_blank" rel="noreferrer">Open in Setup ↗</a>}
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mt-8">
        <div className="lg:col-span-1">
          <div className="card p-5">
            <dl className="detail-grid">
              {rows.filter(([, v]) => v != null && v !== "").map(([k, v]) => (<div key={k} className="contents"><dt>{k}</dt><dd>{v}</dd></div>))}
            </dl>
            {(f.description || f.helpText) && <div className="rule mt-4 pt-4 text-sm">
              {f.description && <p><span className="eyebrow block mb-1">Description</span>{f.description}</p>}
              {f.helpText && <p className="mt-3"><span className="eyebrow block mb-1">Help text</span>{f.helpText}</p>}
            </div>}
            {f.formula && <div className="rule mt-4 pt-4"><span className="eyebrow block mb-2">Formula</span><pre className="sql">{f.formula}</pre></div>}
            {f.picklistValues.length > 0 && <div className="rule mt-4 pt-4">
              <span className="eyebrow block mb-2">Picklist values ({f.picklistValues.filter((p) => p.active).length} active)</span>
              <div className="flex flex-wrap gap-1">{f.picklistValues.map((p) => <span key={p.value} className={`chip ${p.active ? "" : "opacity-50 line-through"}`} title={p.value}>{p.label}</span>)}</div>
            </div>}
          </div>
        </div>

        <div className="lg:col-span-2">
          <Section title="Marketing Cloud journeys" eyebrow={`${f.sfmc.journeys.length} published journey${f.sfmc.journeys.length === 1 ? "" : "s"}`}>
            {f.sfmc.journeys.length === 0 ? <Empty>{f.sfmc.syncedDE ? "Synced to Marketing Cloud, but no published journey, email, push, SMS or decision split references this column." : "Not in the Marketing Cloud sync, so no journey can read it."}</Empty> : (
              <div className="space-y-3">
                {f.sfmc.journeys.map((j) => {
                  const groups = KIND_ORDER.filter((k) => j.items.some((i) => i.kind === k));
                  return (
                    <div key={j.id} className="card p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Link href={journeyHref(j.id)} className="font-medium hover:underline decoration-[var(--accent)]">{j.name}</Link>
                        <Chip>{j.status}</Chip>
                      </div>
                      <div className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                        {groups.map((k) => (
                          <div key={k}>
                            <div className="eyebrow mb-1">{KIND_LABEL[k] || k}</div>
                            <ul className="space-y-0.5">
                              {j.items.filter((i) => i.kind === k).map((i, idx) => (
                                <li key={idx} className="flex items-baseline gap-2"><span className="dot shrink-0 mt-1.5" style={{ background: "var(--accent)" }} /><span className="mono break-all">{i.name}</span><span className="text-xs text-ink-3 whitespace-nowrap">{i.how}</span></li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>

          <Section title="Marketing Cloud SQL queries" eyebrow={`${f.sfmc.queries.length} quer${f.sfmc.queries.length === 1 ? "y" : "ies"} read ${f.sfmc.syncedDE || "the synced DE"}`}>
            {f.sfmc.queries.length === 0 ? <Empty>No query activity references this column.</Empty> : (
              <div className="table-wrap card"><table className="dd"><thead><tr><th>Query</th><th>Writes to</th><th>Automation</th></tr></thead><tbody>
                {f.sfmc.queries.map((q) => (<tr key={q.id}><td><Link href={`/queries/${q.id}/`} className="mono hover:underline decoration-[var(--accent)]">{q.name}</Link></td><td className="mono text-ink-2">{q.targetDE}</td><td className="text-ink-2">{q.automations.join(", ") || <span className="text-ink-3">not in an automation</span>}</td></tr>))}
              </tbody></table></div>
            )}
          </Section>

          <Section title="Data Cloud" eyebrow={f.dc.stream ? `${dcCount} downstream reference${dcCount === 1 ? "" : "s"}` : "not ingested"}>
            {!f.dc.stream ? <Empty>The CRM data stream for {objectLabel(f.object)} does not include this field.</Empty> : (
              <div className="space-y-4 text-sm">
                <div className="card p-4">
                  <div className="eyebrow mb-2">Lineage</div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="chip chip-fill">{f.object}.{f.apiName}</span><span className="text-ink-3">→</span>
                    <span className="chip" title="Data lake object column">{f.dc.dloField}</span>
                    {f.dc.dmoFields.length > 0 && <span className="text-ink-3">→</span>}
                    {f.dc.dmoFields.map((m) => <span key={m.dmoField} className="chip chip-accent2" title={m.method}>{m.dmoField}<span className="text-ink-3 font-normal"> · {m.method}</span></span>)}
                    {f.dc.dmoFields.length === 0 && <span className="text-ink-3 text-xs">no data model object field mapped</span>}
                  </div>
                </div>
                <UsageList title="Calculated insights" items={f.dc.calculatedInsights.map((c) => ({ key: c.apiName, node: <Link href={ciHref(c.apiName)} className="hover:underline decoration-[var(--accent)]"><span className="mono">{c.apiName}</span> <span className="text-ink-3">{c.displayName}</span></Link> }))} />
                <UsageList title="Segments" items={f.dc.segments.map((s) => ({ key: s.apiName, node: <Link href={`/data-cloud/#segment-${s.apiName}`} className="hover:underline decoration-[var(--accent)]"><span className="mono">{s.apiName}</span> <span className="text-ink-3">{s.displayName}</span></Link> }))} />
                <UsageList title="Identity resolution" items={f.dc.identityResolution.map((r, i) => ({ key: String(i), node: <span>{r.ruleset} · {r.type}: <span className="mono">{r.rule}</span>{r.object ? <span className="text-ink-3"> on {r.object}</span> : null}</span> }))} />
                <UsageList title="Activations" items={f.dc.activations.map((a) => ({ key: a.name, node: <span>{a.name} <span className="text-ink-3">→ {a.target} (segment {a.segment})</span></span> }))} />
                <UsageList title="Data graphs" items={f.dc.dataGraphs.map((g) => ({ key: g.name, node: <span className="mono">{g.name}</span> }))} />
                <UsageList title="Data actions" items={f.dc.dataActions.map((g) => ({ key: g.name, node: <span className="mono">{g.name}</span> }))} />
                {dcCount === 0 && <Empty>Ingested, but no calculated insight, segment, identity rule, activation, data graph or data action references the mapped model fields.</Empty>}
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

function UsageList({ title, items }: { title: string; items: { key: string; node: React.ReactNode }[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="eyebrow mb-1">{title} · {items.length}</div>
      <ul className="space-y-0.5">{items.map((i) => <li key={i.key} className="flex items-baseline gap-2"><span className="dot shrink-0 mt-1.5" style={{ background: "var(--accent-2)" }} />{i.node}</li>)}</ul>
    </div>
  );
}
