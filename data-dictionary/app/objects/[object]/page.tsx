import Link from "next/link";
import { data, objectsByName } from "@/lib/data";
import { toRow } from "@/lib/rows";
import { FieldTable } from "@/components/FieldTable";
import { Breadcrumbs, Stat } from "@/components/ui";

export function generateStaticParams() { return data.objects.map((o) => ({ object: o.apiName })); }
export async function generateMetadata({ params }: { params: Promise<{ object: string }> }) {
  const { object } = await params;
  return { title: objectsByName.get(object)?.label ?? object };
}

export default async function ObjectPage({ params }: { params: Promise<{ object: string }> }) {
  const { object } = await params;
  const o = objectsByName.get(object)!;
  const rows = data.fields.filter((f) => f.object === object).map(toRow);
  const stream = data.streams.find((s) => s.object === object);
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Objects" }, { label: o.label }]} />
      <div className="flex flex-wrap items-center gap-2 mb-1">
        {data.objects.map((x) => (
          <Link key={x.apiName} href={`/objects/${x.apiName}/`} className="chip hover:border-[var(--accent)]" aria-current={x.apiName === object ? "page" : undefined} style={x.apiName === object ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined}>{x.label}</Link>
        ))}
      </div>
      <h1 className="h-display text-4xl mt-4">{o.label} <span className="mono text-base text-ink-3 font-normal">{o.apiName}</span></h1>
      <p className="text-ink-2 mt-2 text-sm">
        {o.syncedDE ? <>Synced to Marketing Cloud as <span className="mono">{o.syncedDE}</span> ({o.stats.inSfmc} fields). </> : "Not synced to Marketing Cloud. "}
        {stream ? <>Ingested to Data Cloud by stream <span className="mono">{stream.name}</span> into <span className="mono">{stream.dlo}</span> ({stream.mappedFields} fields, {stream.totalRecords.toLocaleString()} records{o.dmos.length ? `, mapped to ${o.dmos.join(", ")}` : ", no model object mapping detected"}).</> : "Not ingested to Data Cloud."}
      </p>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5 mb-8">
        <Stat label="Fields" value={o.fieldCount} hint={`${o.customCount} custom`} />
        <Stat label="In journeys" value={o.stats.usedInJourneys} />
        <Stat label="In queries" value={o.stats.usedInQueries} />
        <Stat label="In Data Cloud logic" value={o.stats.usedInDataCloud} hint="CI, segment, identity, graph, action" />
        <Stat label="No usage found" value={o.stats.unused} />
      </div>
      <FieldTable rows={rows} />
    </div>
  );
}
