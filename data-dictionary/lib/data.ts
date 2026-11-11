import dictionary from "@/data/dictionary.json";

export type UsageItem = { kind: string; name: string; how: string };
export type JourneyUse = { id: string; name: string; status: string; items: UsageItem[] };
export type QueryUse = { id: string; name: string; targetDE: string | null; automations: string[] };
export type Field = {
  key: string; object: string; apiName: string; label: string; type: string; typeDetail: string; custom: boolean;
  length?: number | null; precision?: number | null; scale?: number | null; required?: boolean; unique?: boolean; externalId?: boolean;
  picklistValues: { value: string; label: string; active: boolean }[]; formula?: string | null; defaultValue?: unknown;
  definition: string; definitionSource: "dictionary" | "salesforce" | null; definitionConfidence?: string | null;
  description: string; helpText: string; referenceTo: string[]; relationshipName?: string | null;
  createdDate?: string | null; createdBy?: string | null; lastModifiedDate?: string | null; lastModifiedBy?: string | null;
  historyTracked?: boolean | null; businessStatus?: string | null; businessOwner?: string | null; securityClassification?: string | null; complianceGroup?: string | null;
  namespace?: string | null; setupUrl: string; updateable?: boolean; createable?: boolean;
  sfmc: { syncedDE: string | null; queries: QueryUse[]; journeys: JourneyUse[] };
  dc: { stream: string | null; dloField: string | null; dmoFields: { dmoField: string; method: string }[];
    calculatedInsights: { apiName: string; displayName: string }[]; segments: { apiName: string; displayName: string }[];
    identityResolution: { ruleset: string; rule: string; type: string; object?: string }[]; dataGraphs: { name: string; status: string }[];
    dataActions: { name: string }[]; activations: { name: string; target: string; segment: string }[] };
  models?: { id: string; name: string; note: string }[];
  usage: { sfmcJourneys: number; sfmcQueries: number; dc: number; inSfmc: boolean; inDataCloud: boolean };
};
export type ObjectInfo = {
  apiName: string; label: string; pluralLabel?: string; custom?: boolean; fieldCount: number; customCount: number;
  syncedDE: string | null; stream: string | null; dmos: string[];
  stats: { inSfmc: number; inDataCloud: number; usedInJourneys: number; usedInQueries: number; usedInDataCloud: number; defined?: number; unused: number };
};
export type JourneyItem = { kind: string; name: string; activityKey: string | null; fields: { key: string; how: string }[]; unresolvedColumns: string[]; detail: Record<string, unknown> | null };
export type Journey = {
  id: string; name: string; status: string; version: number; modifiedDate: string; createdDate: string; description?: string;
  entry: { type: string; dataExtension: string | null; eventDefinition: string | null; automations: string[] };
  activityCount: number; items: JourneyItem[]; fieldKeys: string[];
};
export type Query = { id: string; name: string; key: string; targetDE: string | null; targetKey: string; targetUpdateType: string | null; sources: string[]; syncedSources: string[]; automations: { id: string; name: string; status: string; schedule: string | null }[]; fields: string[]; modified: string; sqlPreview: string };
export type CI = {
  apiName: string; displayName: string; description: string; status: string; definitionStatus: string; definitionType: string; creationType: string; isEnabled: boolean;
  lastRun: string | null; lastRunStatus: string | null; schedule: string | null; expression: string;
  dimensions: { name: string; label: string; type: string; formula: string }[]; measures: { name: string; label: string; type: string; formula: string }[];
  sourceRefs: string[]; sourceObjects: string[]; referencesCIs: string[]; salesforceFields: string[]; relationships: { fromEntity: string; toEntity: string; fromEntityAttribute?: string; toEntityAttribute?: string }[]; partitionBy?: string | null;
  usedIn: { segments: { apiName: string; displayName: string }[]; calculatedInsights: { apiName: string; displayName: string }[]; dataGraphs: { name: string; status: string }[]; dataActions: { name: string }[]; activations: { name: string; target: string; segment: string }[]; salesforce: { type: string; name: string }[] };
};
export type Segment = { apiName: string; displayName: string; status: string; segmentOn: string; publishInterval: string; publishStatus?: string | null; lastPublish?: string | null; refs: string[]; calculatedInsights: string[]; salesforceFields: string[]; activations: { name: string; target: string; segment: string }[] };
export type ChangeEntry = { date: string; previous: string | null; fieldsAdded: string[]; fieldsRemoved: string[]; cisAdded: string[]; cisRemoved: string[]; journeysAdded: string[]; journeysRemoved: string[]; segmentsAdded: string[]; segmentsRemoved: string[]; fieldLabels?: Record<string, string> };
export type ModelCheck = { id: string; label: string; type: string; state: "ok" | "fail" | "unknown"; observed: string };
export type ModelTask = { title: string; cadence: string; owner: string; nextDue?: string; why: string; steps: string[]; runbook?: string };
export type ModelStep = { what: string; kind: string; transform?: string; ref?: string; schedule: string; automated: boolean; note?: string;
  live?: { lastRun: string | null; lastRunStatus: string | null; runs24h: number; failed24h: number; schedule: { frequency: string; hour: number; minute: number; zone: string; next: string } | null } };
export type Model = {
  id: string; name: string; version: string; stage: string; platform: string; owner: string; summary: string; predicts: string; population: string; usedFor: string; retired?: string;
  components: { name: string; apiName?: string; target: string; trained: string; note?: string; status: string | null; inputs: string[] }[];
  outputs: { field: string; note?: string; known: boolean }[]; chain: ModelStep[];
  consumers: { kind: string; name: string; note?: string; journeyId: string | null }[];
  quality: { verdict: string; summary: string; passLine: string; nextReview?: string; nextReviewWhat?: string };
  validation: { date: string; what: string; metric: string; value: string; baseline: string; result: string; note?: string }[];
  checks: ModelCheck[]; running: "ok" | "fail" | "unknown"; checkedAt: string | null;
  manualTasks: ModelTask[]; openItems: string[]; docs: { label: string; path: string }[];
};
export type OtherModel = { apiName: string; label: string; status: string; capability: string; createdDate: string; inputs: number };
export type Dictionary = {
  generatedAt: string; org: { instanceUrl: string; alias: string }; objects: ObjectInfo[]; fields: Field[]; journeys: Journey[]; queries: Query[];
  calculatedInsights: CI[]; segments: Segment[]; activations: { id: string; name: string; target: string; segment: string; status: string; refreshType: string; lastPublish: string | null; lastPublishStatus: string | null; attributes: string[]; salesforceFields: string[] }[];
  dataGraphs: { name: string; status: string; primaryObject: string; objects: string[]; salesforceFields: string[] }[]; dataActions: { name: string; objects: string[]; salesforceFields: string[] }[];
  streams: { object: string; name: string; dlo: string; status: string; lastRefresh: string; lastRunStatus: string; totalRecords: number; mappedFields: number; refresh: string; dmos: string[] }[];
  transforms: { name: string; label: string; type: string; status: string; lastRun: string | null; lastRunStatus: string | null }[];
  models: Model[]; otherModels: OtherModel[];
  changelog: ChangeEntry[]; summary: { fields: number; journeysReported: number; journeyStatuses: Record<string, number>; queriesWithFields: number; cis: number; segments: number };
};

export const data = dictionary as unknown as Dictionary;
export const fieldsByKey = new Map(data.fields.map((f) => [f.key, f]));
export const objectsByName = new Map(data.objects.map((o) => [o.apiName, o]));
export const journeysById = new Map(data.journeys.map((j) => [j.id, j]));
export const cisByName = new Map(data.calculatedInsights.map((c) => [c.apiName, c]));
export const modelsById = new Map((data.models ?? []).map((m) => [m.id, m]));
export function modelHref(id: string) { return `/models/${id}/`; }
export const RUNNING_LABEL: Record<string, string> = { ok: "Running", fail: "Needs attention", unknown: "Not checked" };
export function runningColor(state: string) { return state === "ok" ? "var(--seafoam)" : state === "fail" ? "var(--accent)" : "var(--horizon)"; }
export function buildDay() { return new Date().toISOString().slice(0, 10); }
export const segmentsByName = new Map(data.segments.map((s) => [s.apiName, s]));

export function fieldHref(key: string) {
  const [obj, ...rest] = key.split(".");
  return `/fields/${obj}/${rest.join(".")}/`;
}
export function objectHref(obj: string) { return `/objects/${obj}/`; }
export function journeyHref(id: string) { return `/journeys/${id}/`; }
export function ciHref(name: string) { return `/calculated-insights/${name}/`; }
export function objectLabel(obj: string) { return objectsByName.get(obj)?.label ?? obj; }
export function fmtDate(s?: string | null) {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
export function fmtDateTime(s?: string | null) {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC" }) + " UTC";
}
export const KIND_LABEL: Record<string, string> = {
  email: "Email", push: "Push", sms: "SMS", query: "SQL query", decision: "Decision split", entry: "Entry", salescloud: "Sales Cloud activity", contactupdate: "Update contact data",
};
