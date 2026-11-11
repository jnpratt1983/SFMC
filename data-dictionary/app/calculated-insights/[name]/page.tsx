import Link from "next/link";
import { data, cisByName, ciHref, fmtDateTime } from "@/lib/data";
import { Breadcrumbs, Chip, Empty, FieldLink, Section, StatusDot } from "@/components/ui";

export function generateStaticParams() { return data.calculatedInsights.map((c) => ({ name: c.apiName })); }
export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  return { title: cisByName.get(name)?.displayName ?? name };
}

export default async function CIPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const c = cisByName.get(name)!;
  const u = c.usedIn;
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { href: "/calculated-insights/", label: "Calculated insights" }, { label: c.apiName }]} />
      <div className="eyebrow">Data Cloud calculated insight · {c.definitionType?.toLowerCase().replace("_", " ")}</div>
      <h1 className="h-display text-4xl mt-1 break-all"><span className="mono text-[0.9em] font-normal">{c.apiName}</span></h1>
      <p className="text-ink-2 text-lg mt-1">{c.displayName}</p>
      {c.description && <p className="text-ink-2 text-sm mt-2 max-w-3xl">{c.description}</p>}
      <div className="flex flex-wrap gap-2 mt-3">
        <Chip tone="fill">{c.status}</Chip><Chip>{c.definitionStatus}</Chip><Chip>{c.schedule}</Chip>
        <span className="chip"><StatusDot status={c.lastRunStatus} /><span className="text-ink-3">{fmtDateTime(c.lastRun)}</span></span>
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <div>
          <Section title="Where it is used" eyebrow="Data Cloud and Salesforce">
            <div className="space-y-3 text-sm">
              <List title="Segments" items={u.segments.map((s) => <Link key={s.apiName} href={`/data-cloud/#segment-${s.apiName}`} className="hover:underline decoration-[var(--accent)]"><span className="mono">{s.apiName}</span> <span className="text-ink-3">{s.displayName}</span></Link>)} />
              <List title="Other calculated insights" items={u.calculatedInsights.map((s) => <Link key={s.apiName} href={ciHref(s.apiName)} className="hover:underline decoration-[var(--accent)]"><span className="mono">{s.apiName}</span></Link>)} />
              <List title="Activations (through its segments)" items={u.activations.map((a, i) => <span key={i}>{a.name} <span className="text-ink-3">→ {a.target}</span></span>)} />
              <List title="Data graphs" items={u.dataGraphs.map((g) => <span key={g.name} className="mono">{g.name}</span>)} />
              <List title="Data actions" items={u.dataActions.map((g) => <span key={g.name} className="mono">{g.name}</span>)} />
              <List title="Flows and Apex" items={u.salesforce.map((g) => <span key={g.name}>{g.type} <span className="mono">{g.name}</span></span>)} />
              {!(u.segments.length || u.calculatedInsights.length || u.activations.length || u.dataGraphs.length || u.dataActions.length || u.salesforce.length) && <Empty>No segment, insight, data graph, data action, activation, flow or Apex class references this insight. It may be read directly through the query API or Tableau/CRM Analytics, which the dictionary cannot see.</Empty>}
            </div>
          </Section>
          <Section title="Reads" eyebrow={`${c.sourceObjects.length} objects · ${c.salesforceFields.length} Salesforce fields`}>
            <div className="text-sm">
              <div className="flex flex-wrap gap-1 mb-3">{c.sourceObjects.map((o) => <span key={o} className={`chip ${o.endsWith("__cio") ? "chip-accent" : ""}`}>{o.endsWith("__cio") ? <Link href={ciHref(o)}>{o}</Link> : o}</span>)}</div>
              {c.salesforceFields.length ? <div className="flex flex-wrap gap-x-5 gap-y-1">{c.salesforceFields.map((k) => <FieldLink key={k} k={k} />)}</div> : <Empty>No dictionary field maps into the model fields this insight reads (it works on derived or unified objects).</Empty>}
            </div>
          </Section>
          <Section title="Shape" eyebrow={`${c.dimensions.length} dimensions · ${c.measures.length} measures`}>
            <div className="table-wrap card"><table className="dd"><thead><tr><th>Role</th><th>Attribute</th><th>Type</th><th>Formula</th></tr></thead><tbody>
              {[...c.dimensions.map((d) => ({ ...d, role: "Dimension" })), ...c.measures.map((d) => ({ ...d, role: "Measure" }))].map((d) => (
                <tr key={d.role + d.name}><td className="text-xs text-ink-3">{d.role}</td><td className="mono">{d.name}</td><td className="text-xs text-ink-2">{d.type}</td><td className="mono text-xs text-ink-2 break-all">{d.formula}</td></tr>
              ))}
            </tbody></table></div>
          </Section>
        </div>
        <div>
          <Section title="SQL expression" eyebrow={c.partitionBy ? `partitioned by ${c.partitionBy}` : "definition"}>
            <pre className="sql">{c.expression}</pre>
          </Section>
          {c.relationships.length > 0 && <Section title="Relationships" eyebrow={`${c.relationships.length}`}>
            <ul className="text-xs text-ink-2 space-y-1">{c.relationships.map((r, i) => <li key={i} className="mono">{r.fromEntity}{r.fromEntityAttribute ? `.${r.fromEntityAttribute}` : ""} → {r.toEntity}{r.toEntityAttribute ? `.${r.toEntityAttribute}` : ""}</li>)}</ul>
          </Section>}
        </div>
      </div>
    </div>
  );
}

function List({ title, items }: { title: string; items: React.ReactNode[] }) {
  if (!items.length) return null;
  return <div><div className="eyebrow mb-1">{title} · {items.length}</div><ul className="space-y-0.5">{items.map((n, i) => <li key={i} className="flex items-baseline gap-2"><span className="dot shrink-0 mt-1.5" style={{ background: "var(--accent-2)" }} />{n}</li>)}</ul></div>;
}
