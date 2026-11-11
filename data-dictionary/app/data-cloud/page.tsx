import Link from "next/link";
import { data, ciHref, fmtDate, objectLabel } from "@/lib/data";
import { Breadcrumbs, Empty, FieldLink, Section, StatusDot } from "@/components/ui";

export const metadata = { title: "Data Cloud" };

export default function DataCloud() {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Data Cloud" }]} />
      <h1 className="h-display text-4xl mb-2">Data Cloud</h1>
      <p className="text-ink-2 text-sm mb-2">How the five objects enter Data Cloud and what is built on them. Calculated insights have <Link href="/calculated-insights/" className="underline decoration-[var(--accent)]">their own page</Link>.</p>

      <Section title="CRM data streams" eyebrow="object → data lake object → data model objects">
        <div className="table-wrap card"><table className="dd"><thead><tr><th>Object</th><th>Stream</th><th>Data lake object</th><th>Mapped fields</th><th>Records</th><th>Model objects</th><th>Last refresh</th></tr></thead><tbody>
          {data.streams.map((s) => (
            <tr key={s.name}>
              <td><Link href={`/objects/${s.object}/`} className="hover:underline decoration-[var(--accent)]">{objectLabel(s.object)}</Link></td>
              <td className="mono text-xs">{s.name}</td><td className="mono text-xs">{s.dlo}</td>
              <td className="tabular-nums">{s.mappedFields}</td><td className="tabular-nums">{s.totalRecords.toLocaleString()}</td>
              <td className="text-xs">{s.dmos.length ? s.dmos.map((d) => <span key={d} className="chip chip-accent2 mr-1 mb-1">{d}</span>) : <span className="text-ink-3">none detected</span>}</td>
              <td className="whitespace-nowrap"><StatusDot status={s.lastRunStatus} /><div className="text-xs text-ink-3">{fmtDate(s.lastRefresh)} · {s.refresh}</div></td>
            </tr>
          ))}
        </tbody></table></div>
        <p className="text-xs text-ink-3 mt-2">Standard fields follow the Salesforce package-kit mappings. Custom fields are matched to model object fields by name, because Data Cloud does not expose custom mappings through its API; a field page labels which rule applied.</p>
      </Section>

      <Section title="Segments" eyebrow={`${data.segments.length} segments`}>
        <div className="space-y-2">
          {data.segments.map((s) => (
            <div key={s.apiName} id={`segment-${s.apiName}`} className="card p-4 text-sm scroll-mt-24">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mono font-medium">{s.apiName}</span><span className="text-ink-3">{s.displayName}</span>
                <span className="chip">{s.status}</span><span className="chip">on {s.segmentOn}</span><span className="chip">{s.publishInterval}</span>
              </div>
              <div className="mt-2 grid sm:grid-cols-3 gap-3 text-xs">
                <div><div className="eyebrow mb-1">Calculated insights</div>{s.calculatedInsights.length ? s.calculatedInsights.map((c) => <Link key={c} href={ciHref(c)} className="mono block hover:underline decoration-[var(--accent)]">{c}</Link>) : <span className="text-ink-3">none</span>}</div>
                <div><div className="eyebrow mb-1">Salesforce fields</div>{s.salesforceFields.length ? s.salesforceFields.map((k) => <div key={k}><FieldLink k={k} /></div>) : <span className="text-ink-3">none directly</span>}</div>
                <div><div className="eyebrow mb-1">Activations</div>{s.activations.length ? s.activations.map((a, i) => <div key={i}>{a.name} → {a.target}</div>) : <span className="text-ink-3">none</span>}</div>
              </div>
              {s.refs.length > 0 && <div className="text-xs text-ink-3 mt-2 break-all">Criteria reference: {s.refs.join(", ")}</div>}
            </div>
          ))}
        </div>
      </Section>

      <Section title="Activations" eyebrow={`${data.activations.length}`}>
        {data.activations.length ? <div className="table-wrap card"><table className="dd"><thead><tr><th>Activation</th><th>Target</th><th>Segment</th><th>Attributes</th><th>Fields</th><th>Last publish</th></tr></thead><tbody>
          {data.activations.map((a) => (<tr key={a.id}><td>{a.name}</td><td>{a.target}</td><td className="mono text-xs">{a.segment}</td><td className="text-xs text-ink-2">{a.attributes.join(", ")}</td><td className="text-xs">{a.salesforceFields.map((k) => <div key={k}><FieldLink k={k} /></div>)}</td><td className="whitespace-nowrap"><StatusDot status={a.lastPublishStatus} /><div className="text-xs text-ink-3">{fmtDate(a.lastPublish)}</div></td></tr>))}
        </tbody></table></div> : <Empty>None.</Empty>}
      </Section>

      <div className="grid md:grid-cols-2 gap-6">
        <Section title="Data graphs" eyebrow={`${data.dataGraphs.length}`}>
          {data.dataGraphs.map((g) => <div key={g.name} className="card p-4 text-sm"><div className="flex items-center gap-2"><span className="mono font-medium">{g.name}</span><StatusDot status={g.status} /></div><div className="text-xs text-ink-3 mt-1">primary {g.primaryObject}</div><div className="flex flex-wrap gap-1 mt-2">{g.objects.map((o) => <span key={o} className={`chip ${o.endsWith("__cio") ? "chip-accent" : ""}`}>{o.endsWith("__cio") ? <Link href={ciHref(o)}>{o}</Link> : o}</span>)}</div></div>)}
        </Section>
        <Section title="Data actions" eyebrow={`${data.dataActions.length}`}>
          {data.dataActions.map((g) => <div key={g.name} className="card p-4 text-sm mb-2"><span className="mono font-medium">{g.name}</span><div className="flex flex-wrap gap-1 mt-2">{g.objects.map((o) => <span key={o} className="chip">{o}</span>)}</div></div>)}
        </Section>
      </div>

      <Section title="Data transforms" eyebrow={`${data.transforms.length} · definitions are not exposed by the API`}>
        <div className="table-wrap card"><table className="dd"><thead><tr><th>Transform</th><th>Type</th><th>Status</th><th>Last run</th></tr></thead><tbody>
          {data.transforms.map((t) => <tr key={t.name}><td><span className="mono">{t.name}</span><div className="text-xs text-ink-3">{t.label}</div></td><td className="text-xs">{t.type}</td><td>{t.status}</td><td className="whitespace-nowrap"><StatusDot status={t.lastRunStatus} /><div className="text-xs text-ink-3">{fmtDate(t.lastRun)}</div></td></tr>)}
        </tbody></table></div>
      </Section>
    </div>
  );
}
