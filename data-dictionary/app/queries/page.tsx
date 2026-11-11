import Link from "next/link";
import { data } from "@/lib/data";
import { Breadcrumbs } from "@/components/ui";

export const metadata = { title: "SQL queries" };

export default function Queries() {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Queries" }]} />
      <h1 className="h-display text-4xl mb-2">Marketing Cloud SQL queries</h1>
      <p className="text-ink-2 text-sm mb-6">{data.queries.length} query activities read at least one dictionary field from a synced Salesforce data extension.</p>
      <div className="table-wrap card"><table className="dd"><thead><tr><th>Query</th><th>Reads</th><th>Writes to</th><th>Automation</th><th>Fields</th></tr></thead><tbody>
        {data.queries.map((q) => (
          <tr key={q.id}>
            <td><Link href={`/queries/${q.id}/`} className="mono hover:underline decoration-[var(--accent)]">{q.name}</Link></td>
            <td className="text-xs text-ink-2">{q.syncedSources.join(", ")}</td>
            <td className="mono text-xs text-ink-2">{q.targetDE}</td>
            <td className="text-xs text-ink-2">{q.automations.map((a) => a.name).join(", ") || <span className="text-ink-3">none</span>}</td>
            <td className="tabular-nums">{q.fields.length}</td>
          </tr>
        ))}
      </tbody></table></div>
    </div>
  );
}
