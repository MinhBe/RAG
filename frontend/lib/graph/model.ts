/* Mô hình của trang knowledge graph: từ vựng, kiểu dữ liệu, và các phép tính thuần
   (ontology, khớp triplet, chuỗi lọc). Không phụ thuộc React hay d3. */

/* ── palette & vocabulary ────────────────────────────────────────────────── */
export const TYPE_COLOR: Record<string, string> = {
  document: "#8b5cf6", chapter: "#ec4899", article: "#3b82f6",
  clause: "#10b981", point: "#f59e0b",
  // chế độ ẩn /pv: bộ câu hỏi phỏng vấn
  group: "#ec4899", item: "#3b82f6", layer: "#8b5cf6", tag: "#10b981",
};
export const DOC_COLOR: Record<string, string> = {
  blld2019: "#3b82f6", blld2012: "#94a3b8", nd145_2020: "#10b981",
};
export const EDGE_COLOR: Record<string, string> = {
  contains: "#cbd5e1", sibling: "#e2e8f0", reworded: "#f59e0b",
  tightened: "#ef4444", replaces: "#8b5cf6", superseded_by: "#f59e0b",
  references: "#06b6d4", in_layer: "#a78bfa", tagged: "#06b6d4",
};
export const TYPE_LABEL: Record<string, string> = {
  document: "Văn bản", chapter: "Chương", article: "Điều",
  clause: "Khoản", point: "Điểm",
  group: "Nhóm", item: "Câu hỏi", layer: "Lớp", tag: "Chủ đề",
};
export const EDGE_LABEL: Record<string, string> = {
  contains: "chứa", sibling: "kế tiếp", reworded: "sửa lời",
  tightened: "siết chặt", replaces: "thay thế", superseded_by: "thay thế",
  references: "dẫn chiếu", in_layer: "thuộc lớp", tagged: "gắn thẻ",
};
export const TYPE_RANK: Record<string, number> = {
  document: 0, chapter: 1, article: 2, clause: 3, point: 4,
  group: 1, item: 2, layer: 3, tag: 4,
};
/* leaves stay tiny dots, like the satellites in the reference demo */
export const NODE_R: Record<string, number> = {
  document: 20, chapter: 13, article: 4.5, clause: 2.8, point: 2.2,
  group: 13, item: 4.5, layer: 10, tag: 3,
};
/* only these take part in the force simulation; everything else fans around them,
   which keeps the cluster count near the reference demo's ~15 instead of 160+ */
export const HUB_TYPES = new Set(["document", "chapter", "group"]);

/* relationship map: a fixed 2-D arrangement, readable at a glance like the demo */
export const ONTO_R = 34;
/* the map sits on a light stage, so the faint structural greys need more weight */
export const ONTO_EDGE_COLOR: Record<string, string> = { ...EDGE_COLOR, contains: "#64748b", sibling: "#94a3b8" };
const ONTO_SLOT: Record<string, [number, number]> = {
  document: [100, 90], chapter: [360, 90], article: [360, 280],
  clause: [100, 280], point: [100, 490],
  group: [100, 90], item: [360, 90], layer: [360, 280], tag: [100, 280],
};
const ONTO_SPARE: [number, number][] = [[360, 490], [230, 610], [580, 280]];
/* direction each type's self-loops open toward, chosen to point into free space */
export const ONTO_LOOP_DIR: Record<string, number> = {
  document: -Math.PI / 2, chapter: -Math.PI / 2, article: 0,
  clause: Math.PI, point: Math.PI / 2,
  group: -Math.PI / 2, item: -Math.PI / 2, layer: 0, tag: Math.PI,
};

/* ── types ───────────────────────────────────────────────────────────────── */
export type GNode = {
  id: string; label: string; doc_id: string; doc_type: string; doc_name?: string;
  level: string; type: string; heading: string; text: string;
  score: number; ghost?: boolean;
  x?: number; y?: number; fx?: number | null; fy?: number | null;
  degree?: number;
};
/* source/target start as ids; d3's forceLink swaps them for node objects in place */
export type GEdge = { source: any; target: any; type: string };
export type GraphData = { nodes: GNode[]; edges: GEdge[] };
export type Triplet = { subject?: string; predicate?: string; object?: string };
export type OntoEdge = { subject: string; predicate: string; object: string; count: number };
export type Ontology = { types: string[]; edges: OntoEdge[]; typeOf: Map<string, string> };
export type Panel = "onto" | "detail" | "filter" | "help" | null;
export type GroupBy = "radial" | "doc" | "level" | "organic";
export type ColorBy = "type" | "doc";
export type Point = { x: number; y: number };

export const sid = (e: GEdge): string => (typeof e.source === "object" ? e.source.id : e.source);
export const tid = (e: GEdge): string => (typeof e.target === "object" ? e.target.id : e.target);

/* yFiles `matchesValue`: a missing criterion is a wildcard */
export const matchesValue = (filter: string | undefined, value: string) => !filter || filter === value;

export const tripletKey = (t: Triplet | null) =>
  t ? `${t.subject || "*"}|${t.predicate || "*"}|${t.object || "*"}` : "";

export const isSubjectOnly = (t: Triplet) => !!t.subject && !t.predicate && !t.object;

/* ── ontology: derived from the data, like yFiles createOntologyGraph ──── */
export function deriveOntology(raw: GraphData): Ontology {
  const typeOf = new Map(raw.nodes.map((n) => [n.id, n.type]));
  const types: string[] = [];
  raw.nodes.forEach((n) => { if (!types.includes(n.type)) types.push(n.type); });
  types.sort((a, b) => (TYPE_RANK[a] ?? 9) - (TYPE_RANK[b] ?? 9));

  const trips = new Map<string, OntoEdge>();
  raw.edges.forEach((e) => {
    const s = typeOf.get(sid(e)), o = typeOf.get(tid(e));
    if (!s || !o || !e.type) return;
    const k = `${s}|${e.type}|${o}`;
    const hit = trips.get(k);
    if (hit) hit.count++;
    else trips.set(k, { subject: s, predicate: e.type, object: o, count: 1 });
  });
  return { types, edges: [...trips.values()], typeOf };
}

/* ── triplet matching — port of yFiles edgeMatchesTriplet ──────────────── */
export function edgeMatches(ontology: Ontology, e: GEdge, t: Triplet): boolean {
  const s = ontology.typeOf.get(sid(e)) || "";
  const o = ontology.typeOf.get(tid(e)) || "";
  // subject-only behaves like getSubjectMatchingItems: both ends share the type
  if (isSubjectOnly(t)) return s === t.subject && o === t.subject;
  return matchesValue(t.subject, s) && matchesValue(t.predicate, e.type) && matchesValue(t.object, o);
}

/* nodes + edges a triplet selects, used by both the hard filter and the fade */
export function matchSet(ontology: Ontology, t: Triplet, nodes: GNode[], edges: GEdge[]) {
  const keepE = edges.filter((e) => edgeMatches(ontology, e, t));
  const keepN = new Set<string>();
  keepE.forEach((e) => { keepN.add(sid(e)); keepN.add(tid(e)); });
  if (isSubjectOnly(t)) {
    nodes.forEach((n) => { if (n.type === t.subject) keepN.add(n.id); });
  }
  return { keepN, keepE };
}

export type ViewFilters = {
  hiddenNodeTypes: Set<string>;
  hiddenEdgeTypes: Set<string>;
  filterTriplet: Triplet | null;
  focusId: string | null;
};

/* ── visibility pipeline: hide types → triplet filter → neighborhood ───── */
export function buildView(raw: GraphData, ontology: Ontology, f: ViewFilters): GraphData {
  let nodes = raw.nodes.filter((n) => !f.hiddenNodeTypes.has(n.type));
  const live = new Set(nodes.map((n) => n.id));
  let edges = raw.edges.filter(
    (e) => !f.hiddenEdgeTypes.has(e.type) && live.has(sid(e)) && live.has(tid(e)),
  );

  if (f.filterTriplet) {
    const { keepN, keepE } = matchSet(ontology, f.filterTriplet, nodes, edges);
    nodes = nodes.filter((n) => keepN.has(n.id));
    edges = keepE;
  }

  if (f.focusId) {
    const focus = f.focusId;
    const near = new Set<string>([focus]);
    edges.forEach((e) => {
      if (sid(e) === focus) near.add(tid(e));
      if (tid(e) === focus) near.add(sid(e));
    });
    nodes = nodes.filter((n) => near.has(n.id));
    edges = edges.filter((e) => near.has(sid(e)) && near.has(tid(e)));
  }

  // fresh objects each pass so d3 never reuses stale source/target refs
  const ids = new Set(nodes.map((n) => n.id));
  return {
    nodes: nodes.map((n) => ({ ...n })),
    edges: edges.filter((e) => ids.has(sid(e)) && ids.has(tid(e)))
                .map((e) => ({ source: sid(e), target: tid(e), type: e.type })),
  };
}

/* ── relationship map ────────────────────────────────────────────────────── */
export function ontoPositions(types: string[]): Record<string, Point> {
  const pos: Record<string, Point> = {};
  let spare = 0;
  types.forEach((t) => {
    const sl = ONTO_SLOT[t] || ONTO_SPARE[spare++ % ONTO_SPARE.length];
    pos[t] = { x: sl[0], y: sl[1] };
  });
  return pos;
}

/* an ontology item is dimmed when a hard filter excludes it */
export function ontoDimmed(filter: Triplet | null, t: string, p?: string, o?: string): boolean {
  if (!filter) return false;
  if (p !== undefined && o !== undefined) {
    return !(matchesValue(filter.subject, t) && matchesValue(filter.predicate, p) && matchesValue(filter.object, o));
  }
  const { subject, object } = filter;
  if (!subject && !object) return false;
  return !(subject === t || object === t);
}

/* ── keyword lookup for the Filter panel ────────────────────────────────── */
export function lookupNodes(nodes: GNode[], query: string, type: string, limit = 80): GNode[] {
  const q = query.trim().toLowerCase();
  if (!q && !type) return [];
  return nodes
    .filter((n) => !type || n.type === type)
    .filter((n) => !q ||
      n.label.toLowerCase().includes(q) ||
      (n.heading || "").toLowerCase().includes(q) ||
      (n.text || "").toLowerCase().includes(q))
    .slice(0, limit);
}

export const typeLabel = (t?: string) => (t ? TYPE_LABEL[t] || t : "*");
export const edgeLabel = (p?: string) => (p ? EDGE_LABEL[p] || p : "*");
