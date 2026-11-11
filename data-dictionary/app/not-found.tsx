import Link from "next/link";
export default function NotFound() {
  return <div className="py-20 text-center"><div className="eyebrow">404</div><h1 className="h-display text-3xl mt-2">Nothing here.</h1><p className="text-ink-2 mt-2 text-sm">The field, journey or insight may have been removed in the latest refresh. <Link href="/" className="underline decoration-[var(--accent)]">Back to search</Link>.</p></div>;
}
