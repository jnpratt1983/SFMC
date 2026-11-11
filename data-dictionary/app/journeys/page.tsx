import Link from "next/link";
import { data, journeyHref, fmtDate } from "@/lib/data";
import { Breadcrumbs, Chip } from "@/components/ui";

export const metadata = { title: "Journeys" };

export default function Journeys() {
  const st = data.summary.journeyStatuses;
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Journeys" }]} />
      <h1 className="h-display text-4xl mb-2">Marketing Cloud journeys</h1>
      <p className="text-ink-2 text-sm mb-6">{data.journeys.length} published journeys, with the dictionary fields each one reads through its entry queries, decision splits, emails, push and SMS. The account also holds {st.Stopped || 0} stopped and {st.Draft || 0} draft journeys, which are not traced.</p>
      <div className="table-wrap card"><table className="dd"><thead><tr><th>Journey</th><th>Entry</th><th>Fields</th><th>Emails</th><th>SMS</th><th>Push</th><th>Modified</th></tr></thead><tbody>
        {data.journeys.map((j) => {
          const c = (k: string) => j.items.filter((i) => i.kind === k).length;
          return (
            <tr key={j.id}>
              <td><Link href={journeyHref(j.id)} className="hover:underline decoration-[var(--accent)]">{j.name}</Link> <span className="text-xs text-ink-3">v{j.version}</span></td>
              <td className="text-ink-2 text-xs"><span className="mono">{j.entry.dataExtension || j.entry.type}</span>{j.entry.automations.length ? <div className="text-ink-3">{j.entry.automations.join(", ")}</div> : null}</td>
              <td className="tabular-nums">{j.fieldKeys.length || <span className="text-ink-3">–</span>}</td>
              <td className="tabular-nums">{c("email") || <span className="text-ink-3">–</span>}</td>
              <td className="tabular-nums">{c("sms") || <span className="text-ink-3">–</span>}</td>
              <td className="tabular-nums">{c("push") || <span className="text-ink-3">–</span>}</td>
              <td className="text-ink-2 whitespace-nowrap">{fmtDate(j.modifiedDate)}</td>
            </tr>
          );
        })}
      </tbody></table></div>
      <p className="text-xs text-ink-3 mt-3"><Chip>Fields</Chip> counts dictionary fields only (Lead, Contact, Account, Bill, Monthly Driving Stats).</p>
    </div>
  );
}
