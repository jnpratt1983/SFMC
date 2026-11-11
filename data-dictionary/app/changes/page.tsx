import Link from "next/link";
import { data, fieldHref, ciHref, fmtDate, objectLabel } from "@/lib/data";
import { Breadcrumbs, Empty, Section } from "@/components/ui";

export const metadata = { title: "Change log" };

export default function Changes() {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Changes" }]} />
      <h1 className="h-display text-4xl mb-2">Change log</h1>
      <p className="text-ink-2 text-sm mb-6">Each monthly refresh is compared with the previous snapshot. Fields, calculated insights, journeys and segments that appeared or disappeared are listed here.</p>
      {data.changelog.map((e) => {
        const n = e.fieldsAdded.length + e.fieldsRemoved.length + e.cisAdded.length + e.cisRemoved.length + e.journeysAdded.length + e.journeysRemoved.length + e.segmentsAdded.length + e.segmentsRemoved.length;
        return (
          <Section key={e.date} title={fmtDate(e.date)} eyebrow={e.previous ? `compared with ${fmtDate(e.previous)}` : "baseline snapshot"}>
            {!e.previous ? <Empty>First snapshot. Differences will appear from the next refresh.</Empty> : n === 0 ? <Empty>No additions or removals.</Empty> : (
              <div className="grid md:grid-cols-2 gap-4 text-sm">
                <Group title="Fields added" items={e.fieldsAdded.map((k) => <Link key={k} href={fieldHref(k)} className="hover:underline decoration-[var(--accent)]"><span className="text-ink-3">{objectLabel(k.split(".")[0])} · </span><span className="mono">{k.split(".").slice(1).join(".")}</span>{e.fieldLabels?.[k] ? <span className="text-ink-3"> {e.fieldLabels[k]}</span> : null}</Link>)} />
                <Group title="Fields removed" items={e.fieldsRemoved.map((k) => <span key={k}><span className="text-ink-3">{objectLabel(k.split(".")[0])} · </span><span className="mono">{k.split(".").slice(1).join(".")}</span>{e.fieldLabels?.[k] ? <span className="text-ink-3"> {e.fieldLabels[k]}</span> : null}</span>)} />
                <Group title="Calculated insights added" items={e.cisAdded.map((k) => <Link key={k} href={ciHref(k)} className="mono hover:underline decoration-[var(--accent)]">{k}</Link>)} />
                <Group title="Calculated insights removed" items={e.cisRemoved.map((k) => <span key={k} className="mono">{k}</span>)} />
                <Group title="Journeys published" items={e.journeysAdded.map((k) => <span key={k}>{k}</span>)} />
                <Group title="Journeys no longer published" items={e.journeysRemoved.map((k) => <span key={k}>{k}</span>)} />
                <Group title="Segments added" items={e.segmentsAdded.map((k) => <span key={k} className="mono">{k}</span>)} />
                <Group title="Segments removed" items={e.segmentsRemoved.map((k) => <span key={k} className="mono">{k}</span>)} />
              </div>
            )}
          </Section>
        );
      })}
    </div>
  );
}

function Group({ title, items }: { title: string; items: React.ReactNode[] }) {
  if (!items.length) return null;
  return <div className="card p-4"><div className="eyebrow mb-2">{title} · {items.length}</div><ul className="space-y-1">{items.map((n, i) => <li key={i}>{n}</li>)}</ul></div>;
}
