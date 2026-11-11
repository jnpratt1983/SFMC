import { data, fmtDate } from "@/lib/data";
import { Breadcrumbs, Chip, FieldLink, Section } from "@/components/ui";

export function generateStaticParams() { return data.queries.map((q) => ({ id: q.id })); }
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: data.queries.find((q) => q.id === id)?.name ?? "Query" };
}

export default async function QueryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const q = data.queries.find((x) => x.id === id)!;
  const journeys = data.journeys.filter((j) => j.items.some((i) => i.kind === "query" && i.name === q.name));
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { href: "/queries/", label: "Queries" }, { label: q.name }]} />
      <div className="eyebrow">Marketing Cloud SQL query activity</div>
      <h1 className="h-display text-4xl mt-1 break-all"><span className="mono text-[0.9em] font-normal">{q.name}</span></h1>
      <div className="flex flex-wrap gap-2 mt-3">
        <Chip tone="fill">writes to {q.targetDE}{q.targetUpdateType ? ` (${q.targetUpdateType})` : ""}</Chip>
        {q.automations.map((a) => <Chip key={a.id}>{a.name} · {a.status}{a.schedule ? ` · ${a.schedule}` : ""}</Chip>)}
        <Chip>modified {fmtDate(q.modified)}</Chip>
      </div>
      <Section title="Dictionary fields read" eyebrow={`${q.fields.length} fields from ${q.syncedSources.join(", ")}`}>
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">{q.fields.map((k) => <FieldLink key={k} k={k} />)}</div>
      </Section>
      <Section title="Feeds these journeys" eyebrow={`${journeys.length} published`}>
        {journeys.length ? <ul className="text-sm space-y-1">{journeys.map((j) => <li key={j.id}><a href={`/journeys/${j.id}/`} className="hover:underline decoration-[var(--accent)]">{j.name}</a></li>)}</ul> : <p className="text-sm text-ink-3 italic">Not in the entry chain of a published journey.</p>}
      </Section>
      <Section title="SQL" eyebrow={`other tables: ${q.sources.filter((s) => !q.syncedSources.map((x) => x.toLowerCase()).includes(s)).join(", ") || "none"}`}>
        <pre className="sql">{q.sqlPreview}</pre>
      </Section>
    </div>
  );
}
