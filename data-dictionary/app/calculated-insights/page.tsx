import Link from "next/link";
import { data, ciHref, fmtDate } from "@/lib/data";
import { Breadcrumbs, StatusDot } from "@/components/ui";

export const metadata = { title: "Calculated insights" };

export default function CIs() {
  const cis = [...data.calculatedInsights].sort((a, b) => a.apiName.localeCompare(b.apiName));
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Calculated insights" }]} />
      <h1 className="h-display text-4xl mb-2">Data Cloud calculated insights</h1>
      <p className="text-ink-2 text-sm mb-6">{cis.length} calculated insights in the default data space, with the objects each reads, the Salesforce fields that reach it, and where it is used (segments, other insights, data graphs, data actions, activations).</p>
      <div className="table-wrap card"><table className="dd"><thead><tr><th>Insight</th><th>Reads</th><th>SF fields</th><th>Used in</th><th>Last run</th><th>Schedule</th></tr></thead><tbody>
        {cis.map((c) => {
          const u = c.usedIn; const n = u.segments.length + u.calculatedInsights.length + u.dataGraphs.length + u.dataActions.length + u.activations.length + u.salesforce.length;
          return (
            <tr key={c.apiName}>
              <td><Link href={ciHref(c.apiName)} className="hover:underline decoration-[var(--accent)]"><span className="mono">{c.apiName}</span></Link><div className="text-xs text-ink-3">{c.displayName}</div></td>
              <td className="text-xs text-ink-2">{c.sourceObjects.join(", ")}</td>
              <td className="tabular-nums">{c.salesforceFields.length || <span className="text-ink-3">–</span>}</td>
              <td className="text-xs text-ink-2">{n ? [u.segments.length && `${u.segments.length} segment${u.segments.length > 1 ? "s" : ""}`, u.calculatedInsights.length && `${u.calculatedInsights.length} CI`, u.dataGraphs.length && `${u.dataGraphs.length} graph`, u.dataActions.length && `${u.dataActions.length} action`, u.activations.length && `${u.activations.length} activation`, u.salesforce.length && `${u.salesforce.length} flow/apex`].filter(Boolean).join(", ") : <span className="text-ink-3">not referenced</span>}</td>
              <td className="whitespace-nowrap"><StatusDot status={c.lastRunStatus} /><div className="text-xs text-ink-3">{fmtDate(c.lastRun)}</div></td>
              <td className="text-xs text-ink-2">{c.schedule}</td>
            </tr>
          );
        })}
      </tbody></table></div>
    </div>
  );
}
