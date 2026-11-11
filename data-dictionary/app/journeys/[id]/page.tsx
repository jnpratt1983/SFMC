import { data, journeysById, fmtDate, KIND_LABEL } from "@/lib/data";
import { Breadcrumbs, Chip, Empty, FieldLink, Section } from "@/components/ui";

export function generateStaticParams() { return data.journeys.map((j) => ({ id: j.id })); }
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: journeysById.get(id)?.name ?? "Journey" };
}

export default async function JourneyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const j = journeysById.get(id)!;
  const queries = j.items.filter((i) => i.kind === "query" || i.kind === "entry");
  const activities = j.items.filter((i) => i.kind !== "query" && i.kind !== "entry");
  const byField = new Map<string, Set<string>>();
  for (const it of j.items) for (const f of it.fields) { if (!byField.has(f.key)) byField.set(f.key, new Set()); byField.get(f.key)!.add(`${KIND_LABEL[it.kind] || it.kind}: ${it.name}`); }
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { href: "/journeys/", label: "Journeys" }, { label: j.name }]} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Marketing Cloud journey · v{j.version}</div>
          <h1 className="h-display text-4xl mt-1">{j.name}</h1>
          {j.description && <p className="text-ink-2 mt-2 text-sm">{j.description}</p>}
        </div>
        <div className="flex flex-wrap gap-2"><Chip tone="fill">{j.status}</Chip><Chip>modified {fmtDate(j.modifiedDate)}</Chip><Chip>{j.activityCount} activities</Chip></div>
      </div>
      <div className="card p-4 mt-6 text-sm grid sm:grid-cols-3 gap-3">
        <div><div className="eyebrow">Entry source</div><div className="mono mt-1">{j.entry.dataExtension || "—"}</div><div className="text-xs text-ink-3">{j.entry.type}{j.entry.eventDefinition ? ` · ${j.entry.eventDefinition}` : ""}</div></div>
        <div><div className="eyebrow">Fed by automations</div><div className="mt-1">{j.entry.automations.length ? j.entry.automations.join(", ") : <span className="text-ink-3">none found</span>}</div></div>
        <div><div className="eyebrow">Dictionary fields referenced</div><div className="text-2xl font-light mt-1 tabular-nums">{j.fieldKeys.length}</div></div>
      </div>

      <Section title="Entry data: queries that fill the entry source" eyebrow={`${queries.length} step${queries.length === 1 ? "" : "s"}`}>
        {queries.length === 0 ? <Empty>No SQL query writes to this journey&apos;s entry data extension (it is filled another way, for example an import or a Salesforce data event).</Empty> : (
          <div className="space-y-3">{queries.map((it, idx) => <ItemCard key={idx} it={it} />)}</div>
        )}
      </Section>
      <Section title="Activities that reference fields" eyebrow={`${activities.length} message and decision activities`}>
        {activities.length === 0 ? <Empty>No message or decision activity references a dictionary field.</Empty> : (
          <div className="space-y-3">{activities.map((it, idx) => <ItemCard key={idx} it={it} />)}</div>
        )}
      </Section>
      <Section title="Fields used by this journey" eyebrow={`${byField.size} fields`}>
        {byField.size === 0 ? <Empty>None.</Empty> : (
          <div className="table-wrap card"><table className="dd"><thead><tr><th>Field</th><th>Where</th></tr></thead><tbody>
            {[...byField.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([k, where]) => (
              <tr key={k}><td className="whitespace-nowrap"><FieldLink k={k} /></td><td className="text-ink-2 text-xs">{[...where].sort().join(" · ")}</td></tr>
            ))}
          </tbody></table></div>
        )}
      </Section>
    </div>
  );
}

function ItemCard({ it }: { it: { kind: string; name: string; fields: { key: string; how: string }[]; unresolvedColumns: string[]; detail: Record<string, unknown> | null } }) {
  const d = it.detail || {};
  const automations = (d.automations as string[] | undefined) || [];
  const paths = (d.paths as string[] | undefined) || [];
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="accent">{KIND_LABEL[it.kind] || it.kind}</Chip>
        <span className="mono font-medium break-all">{it.name}</span>
        {typeof d.depth === "number" && d.depth > 0 && <span className="text-xs text-ink-3">upstream, level {d.depth}</span>}
        {typeof d.targetDE === "string" && <span className="text-xs text-ink-3">→ {d.targetDE}</span>}
        {automations.length > 0 && <span className="text-xs text-ink-3">in {automations.join(", ")}</span>}
      </div>
      {typeof d.subject === "string" && d.subject && <div className="text-xs text-ink-2 mt-1">Subject: {d.subject}</div>}
      {typeof d.message === "string" && d.message && <div className="text-xs text-ink-2 mt-1 whitespace-pre-line">{d.message}</div>}
      {typeof d.filter === "string" && d.filter && <div className="text-xs text-ink-2 mt-1">Filter: {d.filter}</div>}
      {paths.length > 0 && <ul className="text-xs text-ink-2 mt-1 list-disc ml-4">{paths.map((p, i) => <li key={i}>{p}</li>)}</ul>}
      {it.fields.length > 0 ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm">{it.fields.map((f) => <span key={f.key}><FieldLink k={f.key} />{f.how && f.how !== "query" && f.how !== "entry data" ? <span className="text-xs text-ink-3"> · {f.how}</span> : null}</span>)}</div>
      ) : <div className="text-xs text-ink-3 mt-2">No dictionary fields.</div>}
      {it.unresolvedColumns.length > 0 && <div className="text-xs text-ink-3 mt-2">Other columns: {it.unresolvedColumns.join(", ")}</div>}
    </div>
  );
}
