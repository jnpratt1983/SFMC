import { data, objectLabel, type Field } from "@/lib/data";
import type { Row } from "@/components/FieldTable";

export function toRow(f: Field): Row {
  return { key: f.key, apiName: f.apiName, label: f.label, typeDetail: f.typeDetail, custom: f.custom, description: f.description, inSfmc: f.usage.inSfmc, inDataCloud: f.usage.inDataCloud,
    journeys: f.usage.sfmcJourneys, queries: f.usage.sfmcQueries, dc: f.usage.dc, object: f.object, objectLabel: objectLabel(f.object) };
}
export const allRows = data.fields.map(toRow);
