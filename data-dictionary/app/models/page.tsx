import Link from "next/link";
import { data, modelHref, fmtDate, fmtDateTime } from "@/lib/data";
import { Breadcrumbs, Empty, Section } from "@/components/ui";
import { Due, RunningBadge } from "@/components/ModelBits";

export const metadata = { title: "Models" };

export default function Models() {
  const models = data.models ?? [];
  const tasks = models.flatMap((m) => m.manualTasks.map((t) => ({ ...t, model: m })))
    .sort((a, b) => (a.nextDue ?? "9999").localeCompare(b.nextDue ?? "9999"));
  const others = data.otherModels ?? [];
  const enabledOthers = others.filter((o) => o.status === "Enabled");
  const checkedAt = models[0]?.checkedAt;
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Models" }]} />
      <h1 className="h-display text-4xl mb-2">Predictive models</h1>
      <p className="text-ink-2 text-sm max-w-3xl">The {models.length} models that score leads and customers: what each predicts, whether it is running, how well it predicts, and the work a person has to do to keep it current.</p>
      <p className="text-xs text-ink-3 mt-2 mb-6">Running checks were read from the org {checkedAt ? fmtDateTime(checkedAt) : "never"}. Validation results and upkeep tasks are maintained by hand in <span className="mono">models/</span>.</p>

      <div className="grid lg:grid-cols-3 gap-4">
        {models.map((m) => {
          const failing = m.checks.filter((c) => c.state === "fail");
          const next = m.manualTasks.filter((t) => t.nextDue).sort((a, b) => a.nextDue!.localeCompare(b.nextDue!))[0];
          const latest = m.validation[0];
          return (
            <Link key={m.id} href={modelHref(m.id)} className="card p-5 block hover:border-[var(--accent)] transition-colors">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-medium leading-snug">{m.name}</h2>
                <span className="chip chip-fill shrink-0">{m.stage}</span>
              </div>
              <p className="text-sm text-ink-2 mt-2">{m.summary}</p>
              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="eyebrow mb-0.5">Running</dt>
                  <dd><RunningBadge state={m.running} /><span className="text-xs text-ink-3 ml-2">{failing.length ? `${failing.length} of ${m.checks.length} checks failing` : `${m.checks.length} checks`}</span></dd>
                </div>
                <div>
                  <dt className="eyebrow mb-0.5">Predictive quality</dt>
                  <dd>{m.quality.verdict}{latest && <span className="text-xs text-ink-3 block">{latest.metric} {latest.value}{latest.baseline ? ` vs ${latest.baseline}` : ""} · {fmtDate(latest.date)}</span>}</dd>
                </div>
                <div>
                  <dt className="eyebrow mb-0.5">Next manual task</dt>
                  <dd>{next ? <>{next.title}<span className="text-xs text-ink-3 block"><Due date={next.nextDue} /></span></> : <span className="text-ink-3">none dated</span>}</dd>
                </div>
              </dl>
            </Link>
          );
        })}
      </div>

      <Section title="Upkeep calendar" eyebrow={`${tasks.length} manual tasks across the models`}>
        <div className="table-wrap card"><table className="dd"><thead><tr><th>Next due</th><th>Task</th><th>Model</th><th>How often</th><th>Owner</th></tr></thead><tbody>
          {tasks.map((t, i) => (
            <tr key={i}>
              <td><Due date={t.nextDue} /></td>
              <td><Link href={`${modelHref(t.model.id)}#upkeep`} className="hover:underline decoration-[var(--accent)]">{t.title}</Link><div className="text-xs text-ink-3 max-w-xl">{t.why}</div></td>
              <td className="whitespace-nowrap">{t.model.name}</td>
              <td className="text-xs text-ink-2">{t.cadence}</td>
              <td className="whitespace-nowrap">{t.owner}</td>
            </tr>
          ))}
        </tbody></table></div>
        <p className="text-xs text-ink-3 mt-2">After doing a task, move its <span className="mono">nextDue</span> date forward in the model&apos;s file under <span className="mono">models/</span>. Everything not listed here runs on a schedule; each model page shows the schedule and the last run.</p>
      </Section>

      <Section title="Other models in Einstein Studio" eyebrow={`${enabledOthers.length} enabled · ${others.length - enabledOthers.length} disabled`}>
        {others.length ? <div className="table-wrap card"><table className="dd"><thead><tr><th>Model</th><th>Status</th><th>Inputs</th><th>Created</th></tr></thead><tbody>
          {others.map((o) => (
            <tr key={o.apiName}>
              <td>{o.label.replace(/^\(Disabled\) /, "")}<div className="mono text-xs text-ink-3 break-all">{o.apiName}</div></td>
              <td>{o.status === "Enabled" ? <span className="chip chip-accent">Enabled, not documented</span> : <span className="text-ink-3">{o.status}</span>}</td>
              <td className="tabular-nums">{o.inputs}</td>
              <td className="whitespace-nowrap text-xs text-ink-2">{fmtDate(o.createdDate)}</td>
            </tr>
          ))}
        </tbody></table></div> : <Empty>None found.</Empty>}
        <p className="text-xs text-ink-3 mt-2">Custom predictive models that exist in the org but are not one of the models above. An enabled one should either get a page here or be switched off.</p>
      </Section>
    </div>
  );
}
