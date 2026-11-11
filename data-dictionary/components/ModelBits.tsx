import { RUNNING_LABEL, runningColor, fmtDate, buildDay } from "@/lib/data";

export function RunningBadge({ state }: { state: string }) {
  return <span className="inline-flex items-center gap-1.5 text-xs text-ink-2 whitespace-nowrap"><span className="dot" style={{ background: runningColor(state), outline: "1px solid var(--line-strong)" }} />{RUNNING_LABEL[state] ?? state}</span>;
}

/** Due date with an "overdue" flag, judged against the day the site was built. */
export function Due({ date }: { date?: string }) {
  if (!date) return <span className="text-ink-3">when triggered</span>;
  const late = date < buildDay();
  return <span className="whitespace-nowrap">{fmtDate(date)}{late && <span className="chip chip-accent ml-2">overdue</span>}</span>;
}

const RESULT_TONE: Record<string, string> = { pass: "chip chip-fill", fail: "chip chip-accent", early: "chip", superseded: "chip" };
export function ResultChip({ result }: { result: string }) {
  return <span className={RESULT_TONE[result] ?? "chip"}>{result === "early" ? "early read" : result}</span>;
}
