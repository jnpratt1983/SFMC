import Link from "next/link";
import { data, objectHref, modelHref, fmtDate } from "@/lib/data";
import { Search } from "@/components/Search";
import { Qiwi, Section, Stat } from "@/components/ui";
import { RunningBadge } from "@/components/ModelBits";

export default function Home() {
  const s = data.summary;
  const latest = data.changelog[0];
  const totals = data.objects.reduce((a, o) => ({ j: a.j + o.stats.usedInJourneys, q: a.q + o.stats.usedInQueries, d: a.d + o.stats.usedInDataCloud, u: a.u + o.stats.unused }), { j: 0, q: 0, d: 0, u: 0 });
  return (
    <div>
      <div className="relative overflow-hidden card p-6 sm:p-10 mb-8">
        <div className="hero-grid absolute inset-0 opacity-60" aria-hidden />
        <Qiwi className="absolute right-6 top-4 h-40 sm:h-56 opacity-80 hidden sm:block" />
        <div className="relative max-w-2xl">
          <div className="eyebrow mb-2">Salesforce · Marketing Cloud · Data Cloud</div>
          <h1 className="h-display text-4xl sm:text-5xl">Every field, and where it does work.</h1>
          <p className="mt-4 text-ink-2 text-base sm:text-lg">
            Fields on Lead, Contact, Account, Bill and Monthly Driving Stats, traced to the Marketing Cloud queries, journeys, emails, push and SMS that read them, and to the Data Cloud streams, model objects, calculated insights and segments built on them. Refreshed monthly.
          </p>
          <div className="mt-6"><Search big autoFocus /></div>
          <p className="mt-2 text-xs text-ink-3">Tip: press <span className="kbd">/</span> anywhere to search. Try “Projected_First_Month_Bill”, “churn”, or “Push_Enabled”.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Fields" value={s.fields} hint={`${totals.u} with no usage found`} />
        <Stat label="Published journeys" value={s.journeysReported} hint={`${totals.j} fields referenced`} />
        <Stat label="SQL queries" value={s.queriesWithFields} hint={`${totals.q} fields referenced`} />
        <Stat label="Calculated insights" value={s.cis} hint={`${s.segments} segments · ${totals.d} fields reach Data Cloud logic`} />
      </div>

      <Section title="Objects" eyebrow="Browse">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.objects.map((o) => (
            <Link key={o.apiName} href={objectHref(o.apiName)} className="card p-5 hover:border-[var(--accent)] transition-colors block">
              <div className="flex items-baseline justify-between">
                <h3 className="text-lg font-medium">{o.label}</h3>
                <span className="mono text-xs text-ink-3">{o.apiName}</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-ink-2">
                <div><div className="text-2xl font-light tabular-nums text-ink">{o.fieldCount}</div>fields</div>
                <div><div className="text-2xl font-light tabular-nums text-ink">{o.stats.usedInJourneys}</div>in journeys</div>
                <div><div className="text-2xl font-light tabular-nums text-ink">{o.stats.usedInDataCloud}</div>in Data Cloud</div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {o.syncedDE && <span className="chip chip-fill">MC · {o.syncedDE}</span>}
                {o.stream && <span className="chip chip-fill">DC · {o.stream}</span>}
              </div>
            </Link>
          ))}
        </div>
      </Section>

      {(data.models?.length ?? 0) > 0 && (
        <Section title="Predictive models" eyebrow="Health and upkeep" aside={<Link href="/models/" className="text-sm hover:underline decoration-[var(--accent)]">All models and the upkeep calendar →</Link>}>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.models.map((m) => (
              <Link key={m.id} href={modelHref(m.id)} className="card p-5 hover:border-[var(--accent)] transition-colors block">
                <div className="flex items-baseline justify-between gap-2"><h3 className="text-lg font-medium">{m.name}</h3><span className="chip chip-fill shrink-0">{m.stage}</span></div>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2"><RunningBadge state={m.running} /><span>{m.quality.verdict}</span><span>{m.manualTasks.length} manual tasks</span></div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      <Section title="Latest refresh" eyebrow="Living dictionary" aside={<Link href="/changes/" className="text-sm hover:underline decoration-[var(--accent)]">Full change log →</Link>}>
        {latest ? (
          <div className="card p-5 text-sm">
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              <span><b>{fmtDate(latest.date)}</b>{latest.previous ? <span className="text-ink-3"> vs {fmtDate(latest.previous)}</span> : <span className="text-ink-3"> · baseline snapshot</span>}</span>
              <span>Fields <b className="text-[var(--accent)]">+{latest.fieldsAdded.length}</b> / −{latest.fieldsRemoved.length}</span>
              <span>Calculated insights +{latest.cisAdded.length} / −{latest.cisRemoved.length}</span>
              <span>Journeys +{latest.journeysAdded.length} / −{latest.journeysRemoved.length}</span>
            </div>
            <p className="text-ink-3 text-xs mt-2">Journeys counted are those currently published in Marketing Cloud; Data Cloud items are those visible to the API in the default data space.</p>
          </div>
        ) : null}
      </Section>
    </div>
  );
}
