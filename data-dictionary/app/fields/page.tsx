import { allRows } from "@/lib/rows";
import { FieldTable } from "@/components/FieldTable";
import { Breadcrumbs } from "@/components/ui";

export const metadata = { title: "All fields" };

export default function AllFields() {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Fields" }]} />
      <h1 className="h-display text-4xl mb-2">All fields</h1>
      <p className="text-ink-2 text-sm mb-6">{allRows.length} fields across five objects. Filter by name, kind or usage; sort any column.</p>
      <FieldTable rows={allRows} showObject />
    </div>
  );
}
