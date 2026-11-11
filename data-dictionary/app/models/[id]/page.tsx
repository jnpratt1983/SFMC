import Link from "next/link";
import { data, modelsById, journeyHref, fmtDate, fmtDateTime, runningColor } from "@/lib/data";
import { Breadcrumbs, Chip, FieldLink, Section, StatusDot } from "@/components/ui";
import { Due, ResultChip, RunningBadge } from "@/components/ModelBits";

export function generateStaticParams() { return (data.models ?? []).map((m) => ({ id: m.id })); }
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: modelsById.get(id)?.name ?? id };
}

const CHECK_WORD: Record<string, string> = { ok: "OK", fail: "Failing", unknown: "Not checked" };

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const m = modelsById.get(id)!;
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { href: "/models/", label: "Models" }, { label: m.name }]} />
      <div className="eyebrow">Predictive model · {m.platform}</div>
      <h1 className="h-display text-4xl mt-1">{m.name}</h1>
      <p className="text-ink-2 text-lg mt-2 max-w-3xl">{m.summary}</p>
      <div className="flex flex-wrap gap-2 mt-3">
        <Chip tone="fill">{m.stage}</Chip><Chip>{m.version}</Chip><Chip>Owner: {m.owner}</Chip>
        <span className="chip"><RunningBadge state={m.running} /></span>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mt-6 text-sm">
        <div className="card p-4"><div className="eyebrow mb-1">Predicts</div>{m.predicts}</div>
        <div className="card p-4"><div className="eyebrow mb-1">Who is scored</div>{m.population}</div>
        <div className="card p-4"><div className="eyebrow mb-1">Used for</div>{m.usedFor}</div>
      </div>

      <div className="grid lg:grid-cols-2 gap-x-8 [&>*]:min-w-0 [&>section]:mt-10! [&>div>section]:mt-10!">
        <Section title="Is it running" eyebrow={m.checkedAt ? `checked ${fmtDateTime(m.checkedAt)}` : "not checked"}>
          <div className="table-wrap card"><table className="dd"><thead><tr><th>Check</th><th>Result</th><th>Observed</th></tr></thead><tbody>
            {m.checks.map((c) => (
              <tr key={c.id}>
                <td>{c.label}</td>
                <td className="whitespace-nowrap"><span className="inline-flex items-center gap-1.5 text-xs"><span className="dot" style={{ background: runningColor(c.state), outline: "1px solid var(--line-strong)" }} />{CHECK_WORD[c.state]}</span></td>
                <td className="text-xs text-ink-2">{c.observed}</td>
              </tr>
            ))}
          </tbody></table></div>
          <p className="text-xs text-ink-3 mt-2">Read from the org at each refresh, so this shows the state at that moment, not now. Run <span className="mono">npm run refresh:models</span> for a current reading.</p>
        </Section>

        <Section title="Does it predict" eyebrow={m.quality.verdict}>
          <p className="text-sm text-ink-2 mb-3">{m.quality.summary}</p>
          <div className="table-wrap card"><table className="dd"><thead><tr><th>Date</th><th>Read</th><th>Result</th><th>Against</th><th></th></tr></thead><tbody>
            {m.validation.map((v, i) => (
              <tr key={i}>
                <td className="whitespace-nowrap text-xs">{fmtDate(v.date)}</td>
                <td>{v.what}{v.note && <div className="text-xs text-ink-3">{v.note}</div>}</td>
                <td className="whitespace-nowrap tabular-nums">{v.metric} <span className="font-medium">{v.value}</span></td>
                <td className="text-xs text-ink-2">{v.baseline}</td>
                <td><ResultChip result={v.result} /></td>
              </tr>
            ))}
          </tbody></table></div>
          <dl className="text-sm mt-3 space-y-2">
            <div><dt className="eyebrow">Pass line</dt><dd className="text-ink-2">{m.quality.passLine}</dd></div>
            {m.quality.nextReview && <div><dt className="eyebrow">Next read</dt><dd className="text-ink-2"><Due date={m.quality.nextReview} /> · {m.quality.nextReviewWhat}</dd></div>}
          </dl>
        </Section>
      </div>

      <Section id="upkeep" title="Manual upkeep" eyebrow={`${m.manualTasks.length} tasks a person has to do`}>
        <div className="grid lg:grid-cols-2 gap-4">
          {m.manualTasks.map((t, i) => (
            <div key={i} className="card p-5 text-sm">
              <h3 className="font-medium text-base">{t.title}</h3>
              <div className="flex flex-wrap gap-2 mt-2 text-xs"><span className="chip chip-fill">{t.cadence}</span><span className="chip">{t.owner}</span>{t.nextDue && <span className="chip">next <Due date={t.nextDue} /></span>}</div>
              <p className="text-ink-2 mt-3">{t.why}</p>
              <ol className="list-decimal pl-5 mt-3 space-y-1">{t.steps.map((s, j) => <li key={j}>{s}</li>)}</ol>
              {t.runbook && <p className="text-xs text-ink-3 mt-3">Runbook: <span className="mono break-all">{t.runbook}</span></p>}
            </div>
          ))}
        </div>
      </Section>

      <Section title="How it runs" eyebrow="scoring chain, in order">
        <div className="table-wrap card"><table className="dd"><thead><tr><th>Step</th><th>What runs it</th><th>Schedule</th><th>Last run</th></tr></thead><tbody>
          {m.chain.map((s, i) => (
            <tr key={i}>
              <td>{s.what}{s.note && <div className="text-xs text-ink-3 max-w-md">{s.note}</div>}</td>
              <td className="text-xs">{s.kind}<div className="mono text-ink-3 break-all">{s.transform ?? s.ref}</div></td>
              <td className="text-xs">{s.automated ? s.schedule : <span className="chip chip-accent">manual</span>}{!s.automated && <div className="text-ink-3 mt-1">{s.schedule}</div>}</td>
              <td className="whitespace-nowrap">{s.live ? <><StatusDot status={s.live.lastRunStatus} /><div className="text-xs text-ink-3">{fmtDateTime(s.live.lastRun)}</div>{s.automated && <div className="text-xs text-ink-3">{s.live.runs24h} run{s.live.runs24h === 1 ? "" : "s"} in 24 h{s.live.failed24h ? `, ${s.live.failed24h} failed` : ""}</div>}</> : <span className="text-xs text-ink-3">not tracked here</span>}</td>
            </tr>
          ))}
        </tbody></table></div>
      </Section>

      <div className="grid lg:grid-cols-2 gap-x-8 [&>*]:min-w-0 [&>section]:mt-10! [&>div>section]:mt-10!">
        <Section title="Models" eyebrow={`${m.components.length} trained model${m.components.length === 1 ? "" : "s"}`}>
          <div className="space-y-3">
            {m.components.map((c) => (
              <div key={c.name} className="card p-4 text-sm">
                <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{c.name}</span>{c.status && <span className="chip">{c.status}</span>}<span className="text-xs text-ink-3">trained {fmtDate(c.trained)}</span></div>
                {c.apiName && <div className="mono text-xs text-ink-3 break-all mt-1">{c.apiName}</div>}
                <div className="mt-2"><span className="text-ink-3">Target: </span>{c.target}</div>
                {c.note && <p className="text-ink-2 mt-1">{c.note}</p>}
                {c.inputs.length > 0 && <details className="mt-2"><summary className="text-xs text-ink-3 cursor-pointer">{c.inputs.length} inputs</summary><div className="flex flex-wrap gap-1 mt-2">{c.inputs.map((n) => <span key={n} className="chip mono">{n.replace(/__c$/, "")}</span>)}</div></details>}
              </div>
            ))}
            {m.retired && <p className="text-xs text-ink-3">{m.retired}</p>}
          </div>
        </Section>

        <div>
          <Section title="What it writes" eyebrow="Salesforce fields">
            <ul className="space-y-2 text-sm">{m.outputs.map((o) => <li key={o.field}><FieldLink k={o.field} />{o.note && <div className="text-xs text-ink-3">{o.note}</div>}</li>)}</ul>
          </Section>
          <Section title="Where it is used">
            <ul className="space-y-2 text-sm">{m.consumers.map((c) => <li key={c.name}><span className="chip mr-2">{c.kind}</span>{c.journeyId ? <Link href={journeyHref(c.journeyId)} className="hover:underline decoration-[var(--accent)]">{c.name}</Link> : c.name}{c.note && <div className="text-xs text-ink-3 mt-0.5">{c.note}</div>}</li>)}</ul>
          </Section>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-x-8 [&>*]:min-w-0 [&>section]:mt-10! [&>div>section]:mt-10!">
        <Section title="Open items" eyebrow="known gaps, not recurring work">
          <ul className="list-disc pl-5 space-y-1.5 text-sm text-ink-2">{m.openItems.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </Section>
        <Section title="Documents" eyebrow="in the SFMC repo unless noted">
          <ul className="space-y-1.5 text-sm">{m.docs.map((d) => <li key={d.path}>{d.label}<div className="mono text-xs text-ink-3 break-all">{d.path}</div></li>)}</ul>
        </Section>
      </div>
    </div>
  );
}
