"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Script from "next/script";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/* ── palette & vocabulary ────────────────────────────────────────────────── */
const TYPE_COLOR: Record<string, string> = {
  document: "#8b5cf6", chapter: "#ec4899", article: "#3b82f6",
  clause: "#10b981", point: "#f59e0b",
};
const DOC_COLOR: Record<string, string> = {
  blld2019: "#3b82f6", blld2012: "#94a3b8", nd145_2020: "#10b981",
};
const EDGE_COLOR: Record<string, string> = {
  contains: "#cbd5e1", sibling: "#e2e8f0", reworded: "#f59e0b",
  tightened: "#ef4444", replaces: "#8b5cf6", superseded_by: "#f59e0b",
  references: "#06b6d4",
};
const TYPE_LABEL: Record<string, string> = {
  document: "Văn bản", chapter: "Chương", article: "Điều",
  clause: "Khoản", point: "Điểm",
};
const EDGE_LABEL: Record<string, string> = {
  contains: "chứa", sibling: "kế tiếp", reworded: "sửa lời",
  tightened: "siết chặt", replaces: "thay thế", superseded_by: "thay thế",
  references: "dẫn chiếu",
};
const TYPE_RANK: Record<string, number> = {
  document: 0, chapter: 1, article: 2, clause: 3, point: 4,
};
/* leaves stay tiny dots, like the satellites in the reference demo */
const NODE_R: Record<string, number> = {
  document: 20, chapter: 13, article: 4.5, clause: 2.8, point: 2.2,
};
/* only these take part in the force simulation; everything else fans around them,
   which keeps the cluster count near the reference demo's ~15 instead of 160+ */
const HUB_TYPES = new Set(["document", "chapter"]);

/* relationship map: a fixed 2-D arrangement, readable at a glance like the demo */
const ONTO_R = 34;
/* the map sits on a light stage, so the faint structural greys need more weight */
const ONTO_EDGE_COLOR: Record<string, string> = { ...EDGE_COLOR, contains: "#64748b", sibling: "#94a3b8" };
const ONTO_SLOT: Record<string, [number, number]> = {
  document: [100, 90], chapter: [360, 90], article: [360, 280],
  clause: [100, 280], point: [100, 490],
};
const ONTO_SPARE: [number, number][] = [[360, 490], [230, 610], [580, 280]];
/* direction each type's self-loops open toward, chosen to point into free space */
const ONTO_LOOP_DIR: Record<string, number> = {
  document: -Math.PI / 2, chapter: -Math.PI / 2, article: 0,
  clause: Math.PI, point: Math.PI / 2,
};

/* ── types ───────────────────────────────────────────────────────────────── */
type GNode = {
  id: string; label: string; doc_id: string; doc_type: string;
  level: string; type: string; heading: string; text: string;
  score: number; ghost?: boolean;
  x?: number; y?: number; fx?: number | null; fy?: number | null;
  degree?: number;
};
type GEdge = { source: any; target: any; type: string };
type Triplet = { subject?: string; predicate?: string; object?: string };
type OntoEdge = { subject: string; predicate: string; object: string; count: number };
type Menu = { x: number; y: number; kind: "node" | "edge"; node?: string; edge?: OntoEdge };
type Panel = "onto" | "detail" | "filter" | "help" | null;

declare global { interface Window { d3: any } }

const sid = (e: GEdge) => (typeof e.source === "object" ? e.source.id : e.source);
const tid = (e: GEdge) => (typeof e.target === "object" ? e.target.id : e.target);

/* yFiles `matchesValue`: a missing criterion is a wildcard */
const matchesValue = (filter: string | undefined, value: string) => !filter || filter === value;

const tripletKey = (t: Triplet | null) =>
  t ? `${t.subject || "*"}|${t.predicate || "*"}|${t.object || "*"}` : "";

export default function GraphPage() {
  const svgRef   = useRef<SVGSVGElement>(null);
  const simRef   = useRef<any>(null);
  const zoomRef  = useRef<any>(null);
  const nodeSel  = useRef<any>(null);
  const linkSel  = useRef<any>(null);

  const [raw,      setRaw]      = useState<{ nodes: GNode[]; edges: GEdge[] }>({ nodes: [], edges: [] });
  const [input,    setInput]    = useState("");
  const [query,    setQuery]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [d3Ready,  setD3Ready]  = useState(false);
  const [selected, setSelected] = useState<GNode | null>(null);

  /* ontology-driven state, mirroring the yFiles demo */
  const [hiddenNodeTypes, setHiddenNodeTypes] = useState<Set<string>>(new Set());
  const [hiddenEdgeTypes, setHiddenEdgeTypes] = useState<Set<string>>(new Set());
  const [filterTriplet,   setFilterTriplet]   = useState<Triplet | null>(null);
  const [highlight,       setHighlight]       = useState<Triplet | null>(null);
  const [focusId,         setFocusId]         = useState<string | null>(null);
  const [groupBy,         setGroupBy]         = useState<"radial" | "doc" | "level" | "organic">("radial");
  const [colorBy,         setColorBy]         = useState<"type" | "doc">("type");
  const [menu,            setMenu]            = useState<Menu | null>(null);

  /* right-hand collapsible panels */
  const [panel,      setPanel]      = useState<Panel>("onto");
  const [lookup,     setLookup]     = useState("");
  const [lookupType, setLookupType] = useState<string>("");

  /* resizable panel + zoomable relationship map */
  const [sideW, setSideW] = useState(520);
  const [ontoH, setOntoH] = useState(520);
  const [ov,    setOv]    = useState({ k: 1, x: 0, y: 0 });
  const ontoStageRef   = useRef<HTMLDivElement>(null);
  const ontoContentRef = useRef<SVGGElement>(null);
  const userZoomed     = useRef(false);

  useEffect(() => {
    try {
      const w = Number(localStorage.getItem("kgv_sideW"));
      const h = Number(localStorage.getItem("kgv_ontoH"));
      if (w) setSideW(w);
      // no saved height yet: size the map to the screen, not a fixed guess
      setOntoH(h || Math.max(380, Math.min(760, window.innerHeight - 250)));
    } catch { /* storage unavailable: keep defaults */ }
  }, []);

  const fitOnto = useCallback(() => {
    const st = ontoStageRef.current, g = ontoContentRef.current;
    if (!st || !g) return;
    const b = g.getBBox();
    if (!b.width || !b.height) return;
    const top = 44, m = 14;
    const W = st.clientWidth, H = st.clientHeight - top;
    const k = Math.min((W - m * 2) / b.width, (H - m * 2) / b.height, 2.4);
    setOv({ k, x: (W - b.width * k) / 2 - b.x * k, y: top + (H - b.height * k) / 2 - b.y * k });
    userZoomed.current = false;
  }, []);

  const zoomOntoAt = useCallback((f: number, px: number, py: number) => {
    userZoomed.current = true;
    setOv((v) => {
      const k = Math.min(5, Math.max(0.3, v.k * f));
      const r = k / v.k;
      return { k, x: px - (px - v.x) * r, y: py - (py - v.y) * r };
    });
  }, []);

  const zoomOntoCenter = (f: number) => {
    const st = ontoStageRef.current;
    if (st) zoomOntoAt(f, st.clientWidth / 2, st.clientHeight / 2);
  };

  /* shared pointer-drag helper for panning and the two resize handles */
  const startDrag = (e: React.PointerEvent, onMove: (dx: number, dy: number) => void, onEnd?: () => void) => {
    e.preventDefault();
    const sx = e.clientX, sy = e.clientY;
    const move = (m: PointerEvent) => onMove(m.clientX - sx, m.clientY - sy);
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.style.userSelect = "";
      onEnd?.();
    };
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const persist = (key: string, v: number) => { try { localStorage.setItem(key, String(Math.round(v))); } catch { /* ignore */ } };

  /* ── fetch ──────────────────────────────────────────────────────────────── */
  const fetchGraph = useCallback(async (q: string) => {
    setLoading(true);
    try {
      const res  = await fetch(`${API_BASE}/api/graph?query=${encodeURIComponent(q)}&top_k=150`);
      const data = await res.json();
      setRaw({ nodes: data.nodes || [], edges: data.edges || [] });
      setHiddenNodeTypes(new Set()); setHiddenEdgeTypes(new Set());
      setFilterTriplet(null); setHighlight(null); setFocusId(null); setSelected(null);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (d3Ready) fetchGraph(query); }, [d3Ready, query, fetchGraph]);

  /* ── ontology: derived from the data, like yFiles createOntologyGraph ──── */
  const ontology = useMemo(() => {
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
  }, [raw]);

  /* ── triplet matching — port of yFiles edgeMatchesTriplet ──────────────── */
  const edgeMatches = useCallback((e: GEdge, t: Triplet) => {
    const s = ontology.typeOf.get(sid(e)) || "";
    const o = ontology.typeOf.get(tid(e)) || "";
    // subject-only behaves like getSubjectMatchingItems: both ends share the type
    if (t.subject && !t.predicate && !t.object) return s === t.subject && o === t.subject;
    return matchesValue(t.subject, s) && matchesValue(t.predicate, e.type) && matchesValue(t.object, o);
  }, [ontology]);

  /* nodes + edges a triplet selects, used by both the hard filter and the fade */
  const matchSet = useCallback((t: Triplet, nodes: GNode[], edges: GEdge[]) => {
    const keepE = edges.filter((e) => edgeMatches(e, t));
    const keepN = new Set<string>();
    keepE.forEach((e) => { keepN.add(sid(e)); keepN.add(tid(e)); });
    if (t.subject && !t.predicate && !t.object) {
      nodes.forEach((n) => { if (n.type === t.subject) keepN.add(n.id); });
    }
    return { keepN, keepE };
  }, [edgeMatches]);

  /* ── visibility pipeline: hide types → triplet filter → neighborhood ───── */
  const view = useMemo(() => {
    let nodes = raw.nodes.filter((n) => !hiddenNodeTypes.has(n.type));
    const live = new Set(nodes.map((n) => n.id));
    let edges = raw.edges.filter(
      (e) => !hiddenEdgeTypes.has(e.type) && live.has(sid(e)) && live.has(tid(e)),
    );

    if (filterTriplet) {
      const { keepN, keepE } = matchSet(filterTriplet, nodes, edges);
      nodes = nodes.filter((n) => keepN.has(n.id));
      edges = keepE;
    }

    if (focusId) {
      const near = new Set<string>([focusId]);
      edges.forEach((e) => {
        if (sid(e) === focusId) near.add(tid(e));
        if (tid(e) === focusId) near.add(sid(e));
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
  }, [raw, hiddenNodeTypes, hiddenEdgeTypes, filterTriplet, focusId, matchSet]);

  /* ── draw the main graph ────────────────────────────────────────────────── */
  useEffect(() => {
    if (!d3Ready || !svgRef.current) return;
    const d3  = window.d3;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    simRef.current?.stop();

    const nodes: GNode[] = view.nodes;
    const edges: GEdge[] = view.edges as GEdge[];
    if (!nodes.length) { nodeSel.current = null; linkSel.current = null; return; }

    const W = svgRef.current.clientWidth  || 900;
    const H = svgRef.current.clientHeight || 600;
    const CX = W / 2, CY = H / 2;

    const byId = new Map(nodes.map((n) => [n.id, n]));
    const deg: Record<string, number> = {};
    edges.forEach((e) => { deg[sid(e)] = (deg[sid(e)] || 0) + 1; deg[tid(e)] = (deg[tid(e)] || 0) + 1; });
    nodes.forEach((n) => { n.degree = deg[n.id] || 0; });

    const radius = (n: GNode) =>
      HUB_TYPES.has(n.type) ? (NODE_R[n.type] || 8) + Math.log1p(n.degree || 0) * 1.3
                            : (NODE_R[n.type] || 3);
    const color = (n: GNode) =>
      colorBy === "type" ? (TYPE_COLOR[n.type] || "#64748b") : (DOC_COLOR[n.doc_id] || "#64748b");

    /* star substructure: who fans out around whom, by containment */
    const parentOf  = new Map<string, string>();
    const kidsOf    = new Map<string, GNode[]>();
    edges.forEach((e) => {
      if (e.type !== "contains") return;
      const p = byId.get(sid(e)), c = byId.get(tid(e));
      if (!p || !c) return;
      parentOf.set(c.id, p.id);
      (kidsOf.get(p.id) || kidsOf.set(p.id, []).get(p.id)!).push(c);
    });

    const radialMode = groupBy === "radial" || groupBy === "doc";
    // only nodes that are not fanned out around a parent take part in the simulation
    const simNodes = radialMode
      ? nodes.filter((n) => HUB_TYPES.has(n.type) || !parentOf.has(n.id))
      : nodes;
    const simIds   = new Set(simNodes.map((n) => n.id));
    const simEdges = edges.filter((e) => simIds.has(sid(e)) && simIds.has(tid(e)));

    const g = svg.append("g");
    const zoom = d3.zoom().scaleExtent([0.05, 8]).on("zoom", (ev: any) => g.attr("transform", ev.transform));
    svg.call(zoom);
    zoomRef.current = { zoom, svg };

    const defs = svg.append("defs");
    Object.entries(EDGE_COLOR).forEach(([t, c]) => {
      defs.append("marker").attr("id", `ar-${t}`)
        .attr("markerWidth", 7).attr("markerHeight", 7)
        .attr("refX", 13).attr("refY", 3.5).attr("orient", "auto")
        .append("path").attr("d", "M0,0 L0,7 L7,3.5 z").attr("fill", c).attr("opacity", 0.9);
    });

    const spoke = (e: GEdge) => e.type === "contains" || e.type === "sibling";

    const link = g.append("g").attr("fill", "none")
      .selectAll("path").data(edges).enter().append("path")
      .attr("stroke", (e: GEdge) => EDGE_COLOR[e.type] || "#cbd5e1")
      .attr("stroke-width", (e: GEdge) => (spoke(e) ? 0.7 : 1.8))
      .attr("stroke-dasharray", (e: GEdge) => (e.type === "sibling" ? "3,3" : null))
      .attr("stroke-opacity", (e: GEdge) => (spoke(e) ? 0.35 : 0.7))
      .attr("marker-end", (e: GEdge) => (spoke(e) ? null : `url(#ar-${e.type})`));

    const node = g.append("g").selectAll("g").data(nodes).enter().append("g")
      .attr("cursor", "pointer")
      .on("click", (_: any, d: GNode) => { setSelected(d); setPanel("detail"); setMenu(null); })
      .call(d3.drag()
        .on("start", (ev: any, d: GNode) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag",  (ev: any, d: GNode) => { d.fx = ev.x; d.fy = ev.y; })
        .on("end",   (ev: any, d: GNode) => {
          if (!ev.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = groupBy === "level" ? tierY(d) : null;   // keep the tier after a drag
        }));

    node.append("circle")
      .attr("r", radius).attr("fill", color)
      .attr("fill-opacity", (d: GNode) => (HUB_TYPES.has(d.type) ? 0.92 : 0.8))
      .attr("stroke", "#fff")
      .attr("stroke-width", (d: GNode) => (HUB_TYPES.has(d.type) ? 1.8 : 0.5));

    node.append("title").text((d: GNode) => `${TYPE_LABEL[d.type] || d.type} · ${d.heading || d.label}`);

    /* labels only on hubs — unlabelled satellites are what keeps the demo legible */
    const fewArticles = nodes.filter((n) => n.type === "article").length <= 60;
    node.filter((d: GNode) => HUB_TYPES.has(d.type) || (d.type === "article" && fewArticles))
      .append("text")
      .attr("dy", "0.35em").attr("x", (d: GNode) => radius(d) + 5)
      .attr("font-size", (d: GNode) => (d.type === "document" ? "12px" : d.type === "chapter" ? "10px" : "9px"))
      .attr("font-weight", (d: GNode) => (HUB_TYPES.has(d.type) ? "700" : "500"))
      .attr("fill", "var(--foreground,#1e293b)").attr("pointer-events", "none")
      .attr("paint-order", "stroke").attr("stroke", "var(--background,#fff)").attr("stroke-width", 3)
      .text((d: GNode) => {
        const s = d.type === "chapter" ? (d.heading || d.label) : d.label;
        return s.length > 26 ? s.slice(0, 26) + "…" : s;
      });

    nodes.forEach((n) => { n.fx = null; n.fy = null; });

    const ranks = [...new Set(nodes.map((n) => TYPE_RANK[n.type] ?? 9))].sort((a, b) => a - b);
    const tierY = (d: GNode) => H * ((ranks.indexOf(TYPE_RANK[d.type] ?? 9) + 1) / (ranks.length + 1));
    if (groupBy === "level") nodes.forEach((n) => { n.fy = tierY(n); });

    /* children the simulation does not place itself — these form the fan */
    const fanOf = (n: GNode) => (kidsOf.get(n.id) || []).filter((k) => !simIds.has(k.id));

    /* Radius a node needs so its whole subtree fits on an arc without overlap:
       every child claims arc length for its own fan, so nesting stays clean. */
    const SPREAD = Math.PI * 1.6;
    const rMemo = new Map<string, number>();
    const fanRadius = (n: GNode): number => {
      const hit = rMemo.get(n.id);
      if (hit !== undefined) return hit;
      const fan = radialMode ? fanOf(n) : [];
      let r = radius(n);
      if (fan.length) {
        rMemo.set(n.id, r);   // guard against a cycle in malformed data
        const need = fan.reduce((s, k) => s + 2 * (fanRadius(k) + 3), 0);
        r = Math.max(radius(n) + 14, need / SPREAD);
      }
      rMemo.set(n.id, r);
      return r;
    };

    const sim = d3.forceSimulation(simNodes)
      .force("link", d3.forceLink(simEdges).id((d: GNode) => d.id)
        .distance((e: GEdge) => (e.type === "contains" ? 110 : 150))
        .strength(groupBy === "level" ? 0.15 : 0.6))
      .force("charge", d3.forceManyBody().strength(radialMode ? -260 : -260).distanceMax(900))
      .force("collide", d3.forceCollide((d: GNode) => fanRadius(d) + 10));

    if (groupBy === "doc") {
      const docs = [...new Set(simNodes.map((n) => n.doc_id))].sort();
      const cx = (d: GNode) => W * ((docs.indexOf(d.doc_id) + 1) / (docs.length + 1));
      sim.force("x", d3.forceX(cx).strength(0.5)).force("y", d3.forceY(CY).strength(0.05));
    } else if (groupBy === "level") {
      sim.force("x", d3.forceX(CX).strength(0.02));
    } else {
      // real gravity: forceCenter only recentres, it never stops hubs drifting apart
      sim.force("x", d3.forceX(CX).strength(0.08))
         .force("y", d3.forceY(CY).strength(0.08));
    }

    /* fan each hub's children around it, then their own children, recursively */
    function layoutFans() {
      const done = new Set<string>();
      const place = (p: GNode) => {
        const fan = fanOf(p).filter((k) => !done.has(k.id));
        if (!fan.length) return;
        const R = fanRadius(p);
        // spread away from the graph centre so spokes do not cross the hub
        const base = Math.atan2((p.y ?? CY) - CY, (p.x ?? CX) - CX);
        fan.forEach((k, i) => {
          done.add(k.id);
          const a = base + ((i + 0.5) / fan.length - 0.5) * Math.PI * 1.6;
          k.x = (p.x ?? CX) + R * Math.cos(a);
          k.y = (p.y ?? CY) + R * Math.sin(a);
          place(k);
        });
      };
      simNodes.forEach(place);
    }

    const edgePath = (e: GEdge) => {
      const s = e.source as GNode, t = e.target as GNode;
      const sx = s.x ?? 0, sy = s.y ?? 0, tx = t.x ?? 0, ty = t.y ?? 0;
      if (spoke(e)) return `M${sx},${sy}L${tx},${ty}`;
      // bundle long cross-links by bending them toward the centre
      const mx = (sx + tx) / 2, my = (sy + ty) / 2;
      return `M${sx},${sy}Q${mx + (CX - mx) * 0.4},${my + (CY - my) * 0.4} ${tx},${ty}`;
    };

    sim.on("tick", () => {
      if (radialMode) layoutFans();
      link.attr("d", edgePath);
      node.attr("transform", (d: GNode) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    simRef.current = sim; nodeSel.current = node; linkSel.current = link;
    return () => sim.stop();
  }, [view, groupBy, colorBy, d3Ready]);

  /* ── fade pass: highlight never re-lays-out, it only dims (yFiles fadeOut) ─ */
  useEffect(() => {
    if (!nodeSel.current || !linkSel.current) return;
    if (!highlight) {
      nodeSel.current.attr("opacity", 1);
      linkSel.current.attr("stroke-opacity", (e: GEdge) =>
        e.type === "contains" || e.type === "sibling" ? 0.35 : 0.7);
      return;
    }
    const { keepN } = matchSet(highlight, view.nodes, view.edges as GEdge[]);
    nodeSel.current.attr("opacity", (d: GNode) => (keepN.has(d.id) ? 1 : 0.07));
    linkSel.current.attr("stroke-opacity", (e: GEdge) => (edgeMatches(e, highlight) ? 0.95 : 0.03));
  }, [highlight, view, edgeMatches, matchSet]);

  /* ── relationship map geometry ─────────────────────────────────────────── */
  const ontoPos = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    let spare = 0;
    ontology.types.forEach((t) => {
      const sl = ONTO_SLOT[t] || ONTO_SPARE[spare++ % ONTO_SPARE.length];
      pos[t] = { x: sl[0], y: sl[1] };
    });
    return pos;
  }, [ontology.types]);

  /* refit on open, on new data, and on resize unless the user zoomed by hand */
  useEffect(() => {
    if (panel !== "onto") return;
    const st = ontoStageRef.current;
    if (!st) return;
    const id = requestAnimationFrame(fitOnto);
    const ro = new ResizeObserver(() => { if (!userZoomed.current) fitOnto(); });
    ro.observe(st);
    // wheel must be non-passive to stop the panel scrolling while zooming
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = st.getBoundingClientRect();
      zoomOntoAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
    };
    st.addEventListener("wheel", onWheel, { passive: false });
    return () => { cancelAnimationFrame(id); ro.disconnect(); st.removeEventListener("wheel", onWheel); };
  }, [panel, ontology.types, fitOnto, zoomOntoAt]);


  /* an ontology item is dimmed when a hard filter excludes it */
  const ontoDim = useCallback((t: string, p?: string, o?: string) => {
    if (!filterTriplet) return false;
    if (p !== undefined && o !== undefined) {
      return !(matchesValue(filterTriplet.subject, t) &&
               matchesValue(filterTriplet.predicate, p) &&
               matchesValue(filterTriplet.object, o));
    }
    const { subject, object } = filterTriplet;
    if (!subject && !object) return false;
    return !(subject === t || object === t);
  }, [filterTriplet]);

  const toggleNodeType = (t: string) => setHiddenNodeTypes((prev) => {
    const next = new Set(prev);
    if (next.has(t)) next.delete(t); else next.add(t);
    return next;
  });
  const toggleEdgeType = (t: string) => setHiddenEdgeTypes((prev) => {
    const next = new Set(prev);
    if (next.has(t)) next.delete(t); else next.add(t);
    return next;
  });

  const activeFilter = !!(hiddenNodeTypes.size || hiddenEdgeTypes.size || filterTriplet || highlight || focusId);
  const resetAll = () => {
    setHiddenNodeTypes(new Set()); setHiddenEdgeTypes(new Set());
    setFilterTriplet(null); setHighlight(null); setFocusId(null); setMenu(null);
  };

  useEffect(() => {
    if (!menu) return;
    // close only on a press outside the menu, so the menu's own buttons still fire
    const close = (ev: PointerEvent) => {
      if (!(ev.target as Element | null)?.closest?.(".kgv-ctxmenu")) setMenu(null);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [menu]);

  /* ── toolbar zoom controls ──────────────────────────────────────────────── */
  const zoomBy = (k: number) => {
    const z = zoomRef.current; if (!z) return;
    z.svg.transition().duration(220).call(z.zoom.scaleBy, k);
  };
  const zoomFit = () => {
    const z = zoomRef.current, el = svgRef.current; if (!z || !el) return;
    const g = el.querySelector("g"); if (!g) return;
    const b = (g as SVGGElement).getBBox();
    if (!b.width || !b.height) return;
    const k = Math.min(el.clientWidth / b.width, el.clientHeight / b.height) * 0.9;
    const tx = el.clientWidth / 2 - k * (b.x + b.width / 2);
    const ty = el.clientHeight / 2 - k * (b.y + b.height / 2);
    z.svg.transition().duration(350)
      .call(z.zoom.transform, window.d3.zoomIdentity.translate(tx, ty).scale(k));
  };

  /* ── keyword lookup for the Filter panel ────────────────────────────────── */
  const lookupHits = useMemo(() => {
    const q = lookup.trim().toLowerCase();
    if (!q && !lookupType) return [];
    return raw.nodes
      .filter((n) => (!lookupType || n.type === lookupType))
      .filter((n) => !q ||
        n.label.toLowerCase().includes(q) ||
        (n.heading || "").toLowerCase().includes(q) ||
        (n.text || "").toLowerCase().includes(q))
      .slice(0, 80);
  }, [raw.nodes, lookup, lookupType]);

  const focusNode = focusId ? raw.nodes.find((n) => n.id === focusId) : null;
  const togglePanel = (p: Panel) => setPanel((cur) => (cur === p ? null : p));

  return (
    <>
      <Script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"
        strategy="afterInteractive" onLoad={() => setD3Ready(true)} />

      <div className="kgv-shell">
        {/* ── slim header ───────────────────────────────────────────────── */}
        <div className="kgv-topbar">
          <Link href="/" className="kgv-back">← Chat</Link>
          <span className="kgv-title">Knowledge Graph · Luật Lao động</span>
          <span className="kgv-counts">
            <b>{view.nodes.length}</b>/{raw.nodes.length} nodes · <b>{view.edges.length}</b>/{raw.edges.length} edges
          </span>
        </div>

        {/* ── active-filter chips ───────────────────────────────────────── */}
        {activeFilter && (
          <div className="kgv-statbar">
            {filterTriplet && (
              <span className="kgv-chip kgv-chip-filter">
                Lọc: {TYPE_LABEL[filterTriplet.subject || ""] || filterTriplet.subject || "*"}
                {" —"}{EDGE_LABEL[filterTriplet.predicate || ""] || filterTriplet.predicate || "*"}{"→ "}
                {TYPE_LABEL[filterTriplet.object || ""] || filterTriplet.object || "*"}
                <button onClick={() => setFilterTriplet(null)}>✕</button>
              </span>
            )}
            {highlight && (
              <span className="kgv-chip kgv-chip-hl">
                Làm nổi: {TYPE_LABEL[highlight.subject || ""] || highlight.subject || "*"}
                {highlight.predicate &&
                  ` —${EDGE_LABEL[highlight.predicate] || highlight.predicate}→ ${TYPE_LABEL[highlight.object || ""] || highlight.object}`}
                <button onClick={() => setHighlight(null)}>✕</button>
              </span>
            )}
            {[...hiddenNodeTypes].map((t) => (
              <span key={t} className="kgv-chip kgv-chip-hidden">
                Ẩn {TYPE_LABEL[t] || t}<button onClick={() => toggleNodeType(t)}>✕</button>
              </span>
            ))}
            {[...hiddenEdgeTypes].map((t) => (
              <span key={t} className="kgv-chip kgv-chip-hidden">
                Ẩn “{EDGE_LABEL[t] || t}”<button onClick={() => toggleEdgeType(t)}>✕</button>
              </span>
            ))}
            {focusId && (
              <span className="kgv-chip kgv-chip-focus">
                Ngữ cảnh: {focusNode?.label}<button onClick={() => setFocusId(null)}>✕</button>
              </span>
            )}
          </div>
        )}

        <div className="kgv-body">
          <div className="kgv-canvas-wrap">
            {loading && <div className="kgv-loading">Đang tải đồ thị…</div>}
            {!loading && !view.nodes.length && (
              <div className="kgv-loading">Không còn node nào — bộ lọc đang quá chặt.</div>
            )}
            <svg ref={svgRef} className="kgv-svg" />

            {/* ── floating toolbar, as in the reference demo ───────────── */}
            <div className="kgv-toolbar">
              <button title="Thu nhỏ"  onClick={() => zoomBy(1 / 1.4)}>−</button>
              <button title="Phóng to" onClick={() => zoomBy(1.4)}>+</button>
              <button title="Vừa khung" onClick={zoomFit}>⤢</button>
              <button title="Đặt lại bộ lọc" onClick={resetAll} disabled={!activeFilter}>↺</button>
              <span className="kgv-tb-sep" />
              <label>Group By</label>
              <select value={groupBy} onChange={(e) => setGroupBy(e.target.value as any)}>
                <option value="radial">Chương</option>
                <option value="doc">Văn bản</option>
                <option value="level">Cấp độ</option>
                <option value="organic">Tự nhiên</option>
              </select>
              <select value={colorBy} onChange={(e) => setColorBy(e.target.value as any)}>
                <option value="type">Màu: type</option>
                <option value="doc">Màu: văn bản</option>
              </select>
              <span className="kgv-tb-sep" />
              <form onSubmit={(e) => { e.preventDefault(); setQuery(input.trim()); }}>
                <input value={input} onChange={(e) => setInput(e.target.value)}
                  placeholder="Tra cứu điều luật…" />
              </form>
            </div>

          </div>

          {/* ── collapsible right panels ───────────────────────────────── */}
          {panel && (<>
            <div className="kgv-side-resize" title="Kéo để đổi chiều rộng"
              onPointerDown={(e) => {
                const w0 = sideW;
                let w = w0;
                userZoomed.current = false;
                startDrag(e, (dx) => {
                  w = Math.max(300, Math.min(window.innerWidth - 320, w0 - dx));
                  setSideW(w);
                }, () => persist("kgv_sideW", w));
              }} />
            <div className="kgv-side" style={{ width: sideW }}>
              {panel === "onto" && (
              <div className="kgv-onto-block" onPointerDown={(e) => e.stopPropagation()}>
                <div className="kgv-onto-head">
                  <span className="kgv-onto-title">Bản đồ mối quan hệ</span>
                  <span className="kgv-onto-hint">
                    Bấm để làm nổi · chuột phải để lọc / ẩn · cuộn để phóng to · kéo nền để di chuyển
                  </span>
                </div>

                <div className="kgv-onto-stage" ref={ontoStageRef} style={{ height: ontoH }}>
                  <div className="kgv-onto-zoom">
                    <button title="Thu nhỏ" onClick={() => zoomOntoCenter(1 / 1.25)}>−</button>
                    <span>{Math.round(ov.k * 100)}%</span>
                    <button title="Phóng to" onClick={() => zoomOntoCenter(1.25)}>+</button>
                    <button title="Vừa khung" onClick={fitOnto}>⤢</button>
                    <span className="kgv-tb-sep" />
                    <button title="Đặt lại bộ lọc" onClick={resetAll} disabled={!activeFilter}>↺</button>
                  </div>

                  <svg className="kgv-onto-svg">
                    <defs>
                      {Object.entries(ONTO_EDGE_COLOR).map(([t, c]) => (
                        <marker key={t} id={`oar-${t}`} viewBox="0 0 10 10" refX="9" refY="5"
                          markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto">
                          <path d="M0,0 L10,5 L0,10 z" fill={c} />
                        </marker>
                      ))}
                    </defs>

                    <rect className="kgv-onto-bg" width="100%" height="100%" fill="transparent"
                      onClick={() => setMenu(null)}
                      onPointerDown={(e) => {
                        const v0 = ov;
                        startDrag(e, (dx, dy) => {
                          userZoomed.current = true;
                          setOv({ ...v0, x: v0.x + dx, y: v0.y + dy });
                        });
                      }} />

                    <g transform={`translate(${ov.x},${ov.y}) scale(${ov.k})`}>
                      <g ref={ontoContentRef}>
                        {ontology.edges.map((oe) => {
                          const a = ontoPos[oe.subject], b = ontoPos[oe.object];
                          if (!a || !b) return null;
                          const R = ONTO_R;
                          const off = hiddenEdgeTypes.has(oe.predicate) ||
                            hiddenNodeTypes.has(oe.subject) || hiddenNodeTypes.has(oe.object);
                          const dim = ontoDim(oe.subject, oe.predicate, oe.object);
                          const hl  = !!highlight?.predicate && tripletKey(highlight) === tripletKey(oe);
                          const c   = ONTO_EDGE_COLOR[oe.predicate] || "#94a3b8";
                          const key = `${oe.subject}|${oe.predicate}|${oe.object}`;
                          const cls = `kgv-onto-edge${off ? " off" : ""}${dim ? " dim" : ""}${hl ? " hl" : ""}`;
                          const label = EDGE_LABEL[oe.predicate] || oe.predicate;
                          const tip = `${TYPE_LABEL[oe.subject] || oe.subject} —${label}→ ${TYPE_LABEL[oe.object] || oe.object} (${oe.count})`;
                          const onClick = () => { if (!off) { setHighlight({ ...oe }); setMenu(null); } };
                          const onCtx = (ev: React.MouseEvent) => {
                            ev.preventDefault();
                            const r = (ev.currentTarget as Element).closest(".kgv-onto-block")!.getBoundingClientRect();
                            setMenu({ x: ev.clientX - r.left, y: ev.clientY - r.top, kind: "edge", edge: oe });
                          };

                          let d: string, lx: number, ly: number;
                          if (oe.subject === oe.object) {
                            /* self-loop, opening toward the type's free side */
                            const loops = ontology.edges.filter((x) => x.subject === x.object && x.subject === oe.subject);
                            const i = loops.indexOf(oe);
                            const th = (ONTO_LOOP_DIR[oe.subject] ?? 0) + [0, 0.95, -0.95, 1.9, -1.9][i % 5];
                            const P = (ang: number, dist: number) => [a.x + Math.cos(ang) * dist, a.y + Math.sin(ang) * dist];
                            const [sx, sy] = P(th - 0.42, R), [ex, ey] = P(th + 0.42, R);
                            const [c1x, c1y] = P(th - 0.62, R + 72), [c2x, c2y] = P(th + 0.62, R + 72);
                            d = `M${sx},${sy} C${c1x},${c1y} ${c2x},${c2y} ${ex},${ey}`;
                            [lx, ly] = P(th, R + 62);
                          } else {
                            /* parallel relations between one pair of types bow apart, and their
                               labels are staggered along the curve so none sit on another */
                            const pair = [oe.subject, oe.object].sort();
                            const para = ontology.edges.filter(
                              (x) => x.subject !== x.object && [x.subject, x.object].sort().join("|") === pair.join("|"),
                            );
                            const i = para.indexOf(oe), n = para.length;
                            const bend = (i - (n - 1) / 2) * 46;
                            const A = ontoPos[pair[0]], B = ontoPos[pair[1]];
                            const len = Math.hypot(B.x - A.x, B.y - A.y) || 1;
                            const nx = -(B.y - A.y) / len, ny = (B.x - A.x) / len;
                            const qx = (a.x + b.x) / 2 + nx * bend * 2, qy = (a.y + b.y) / 2 + ny * bend * 2;
                            const unit = (fx: number, fy: number) => {
                              const l = Math.hypot(qx - fx, qy - fy) || 1;
                              return [(qx - fx) / l, (qy - fy) / l];
                            };
                            const [ux, uy] = unit(a.x, a.y), [vx, vy] = unit(b.x, b.y);
                            const sx = a.x + ux * R, sy = a.y + uy * R, ex = b.x + vx * R, ey = b.y + vy * R;
                            d = `M${sx},${sy} Q${qx},${qy} ${ex},${ey}`;
                            const t = n > 1 ? 0.5 + (i - (n - 1) / 2) * 0.18 : 0.5;
                            lx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * qx + t * t * ex;
                            ly = (1 - t) ** 2 * sy + 2 * (1 - t) * t * qy + t * t * ey;
                          }

                          const fs = 14, pw = label.length * fs * 0.56 + 18, ph = fs + 10;
                          return (
                            <g key={key} className={cls} onClick={onClick} onContextMenu={onCtx}>
                              <path d={d} fill="none" stroke={c} strokeWidth={2.2}
                                strokeDasharray={off ? "5,4" : undefined} markerEnd={`url(#oar-${oe.predicate})`} />
                              <path d={d} fill="none" stroke="transparent" strokeWidth={14} />
                              <rect x={lx - pw / 2} y={ly - ph / 2} width={pw} height={ph} rx={ph / 2}
                                fill="var(--card,#fff)" stroke={c} strokeWidth={1.4} />
                              <text x={lx} y={ly} dy="0.35em" textAnchor="middle" fontSize={fs}
                                fontWeight={500} fill="var(--foreground,#0f172a)">{label}</text>
                              <title>{tip}</title>
                            </g>
                          );
                        })}

                        {ontology.types.map((t) => {
                          const p = ontoPos[t]; if (!p) return null;
                          const off = hiddenNodeTypes.has(t);
                          const dim = ontoDim(t);
                          const hl  = !!highlight && !highlight.predicate && highlight.subject === t;
                          const n = raw.nodes.filter((x) => x.type === t).length;
                          const name = TYPE_LABEL[t] || t;
                          const fs = 15, pw = name.length * fs * 0.6 + 14, ph = fs + 10;
                          return (
                            <g key={t} className={`kgv-onto-node${off ? " off" : ""}${dim ? " dim" : ""}${hl ? " hl" : ""}`}
                               onClick={() => { if (!off) { setHighlight({ subject: t }); setMenu(null); } }}
                               onContextMenu={(ev) => {
                                 ev.preventDefault();
                                 const r = (ev.currentTarget as Element).closest(".kgv-onto-block")!.getBoundingClientRect();
                                 setMenu({ x: ev.clientX - r.left, y: ev.clientY - r.top, kind: "node", node: t });
                               }}>
                              <circle cx={p.x} cy={p.y} r={ONTO_R} fill={TYPE_COLOR[t] || "#64748b"}
                                stroke="#fff" strokeWidth={3} strokeDasharray={off ? "6,4" : undefined} />
                              <rect x={p.x - pw / 2} y={p.y - ph / 2} width={pw} height={ph} rx={ph / 2}
                                fill="#fff" fillOpacity={0.94} pointerEvents="none" />
                              <text x={p.x} y={p.y} dy="0.35em" textAnchor="middle" fontSize={fs}
                                fontWeight={700} fill="#0f172a" pointerEvents="none">{name}</text>
                              <text x={p.x} y={p.y + ONTO_R + 17} textAnchor="middle" fontSize={13}
                                fill="var(--muted-foreground,#64748b)" pointerEvents="none">{n} node</text>
                              <title>{`${name} — ${n} node`}</title>
                            </g>
                          );
                        })}
                      </g>
                    </g>
                  </svg>
                </div>

                <div className="kgv-onto-hresize" title="Kéo để đổi chiều cao bản đồ"
                  onPointerDown={(e) => {
                    const h0 = ontoH;
                    let h = h0;
                    userZoomed.current = false;
                    startDrag(e, (_, dy) => {
                      h = Math.max(260, Math.min(1400, h0 + dy));
                      setOntoH(h);
                    }, () => persist("kgv_ontoH", h));
                  }} />
  
                {menu && (
                  <div className="kgv-ctxmenu" style={{ left: Math.max(8, Math.min(menu.x, sideW - 230)), top: menu.y + 6 }}
                       onPointerDown={(e) => e.stopPropagation()}>
                    {menu.kind === "edge" && menu.edge && (() => {
                      const oe = menu.edge!;
                      const isFiltered = tripletKey(filterTriplet) === tripletKey(oe);
                      const blocked = hiddenEdgeTypes.has(oe.predicate) ||
                        hiddenNodeTypes.has(oe.subject) || hiddenNodeTypes.has(oe.object);
                      return (
                        <>
                          <button disabled={blocked}
                            onClick={() => { setFilterTriplet(isFiltered ? null : { ...oe }); setHighlight(null); setMenu(null); }}>
                            {isFiltered ? "Bỏ lọc triplet" : "Lọc triplet này"}
                          </button>
                          <button onClick={() => { toggleEdgeType(oe.predicate); setMenu(null); }}>
                            {hiddenEdgeTypes.has(oe.predicate) ? "Hiện" : "Ẩn"} quan hệ “{EDGE_LABEL[oe.predicate] || oe.predicate}”
                          </button>
                        </>
                      );
                    })()}
                    {menu.kind === "node" && menu.node && (
                      <>
                        <button onClick={() => { setFilterTriplet({ subject: menu.node }); setHighlight(null); setMenu(null); }}>
                          Lọc chỉ “{TYPE_LABEL[menu.node] || menu.node}”
                        </button>
                        <button onClick={() => { toggleNodeType(menu.node!); setMenu(null); }}>
                          {hiddenNodeTypes.has(menu.node) ? "Hiện" : "Ẩn"} type “{TYPE_LABEL[menu.node] || menu.node}”
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
              )}
              {panel === "detail" && (
                selected ? (
                  <>
                    <div className="kgv-side-title">Chi tiết</div>
                    <div className="kgv-ctx-badges">
                      <span className="kgv-ctx-badge" style={{ background: TYPE_COLOR[selected.type] || "#64748b" }}>
                        {TYPE_LABEL[selected.type] || selected.type}
                      </span>
                      <span className="kgv-ctx-badge" style={{ background: DOC_COLOR[selected.doc_id] || "#64748b" }}>
                        {selected.doc_id}
                      </span>
                    </div>
                    <div className="kgv-ctx-id">{selected.id}</div>
                    <div className="kgv-ctx-heading">{selected.heading || selected.label}</div>
                    <div className="kgv-ctx-text">{selected.text || "Không có nội dung."}</div>
                    {selected.score > 0 && <div className="kgv-ctx-score">Độ liên quan: {selected.score}</div>}
                    <button
                      className={`kgv-ctx-focus-btn ${focusId === selected.id ? "active" : ""}`}
                      onClick={() => setFocusId((p) => (p === selected.id ? null : selected.id))}>
                      {focusId === selected.id ? "↩ Bỏ ngữ cảnh" : "🔍 Xem ngữ cảnh node này"}
                    </button>
                  </>
                ) : (
                  <>
                    <div className="kgv-side-title">Chi tiết</div>
                    <p className="kgv-side-empty">Chọn một node trên đồ thị để xem nội dung.</p>
                  </>
                )
              )}

              {panel === "filter" && (
                <>
                  <div className="kgv-side-title">Bộ lọc</div>
                  <input className="kgv-side-input" value={lookup} autoFocus
                    onChange={(e) => setLookup(e.target.value)}
                    placeholder="Tra từ khóa trong nội dung…" />
                  <div className="kgv-side-types">
                    <button className={lookupType === "" ? "on" : ""} onClick={() => setLookupType("")}>Tất cả</button>
                    {ontology.types.map((t) => (
                      <button key={t} className={lookupType === t ? "on" : ""}
                        style={lookupType === t ? { background: TYPE_COLOR[t], borderColor: TYPE_COLOR[t] } : undefined}
                        onClick={() => setLookupType(lookupType === t ? "" : t)}>
                        {TYPE_LABEL[t] || t}
                      </button>
                    ))}
                  </div>
                  <div className="kgv-side-count">
                    {lookup || lookupType ? `${lookupHits.length} kết quả` : "Nhập từ khóa hoặc chọn type."}
                  </div>
                  <div className="kgv-side-list">
                    {lookupHits.map((n) => (
                      <button key={n.id} className="kgv-hit"
                        onClick={() => { setSelected(n); setFocusId(n.id); }}>
                        <span className="kgv-hit-dot" style={{ background: TYPE_COLOR[n.type] }} />
                        <span className="kgv-hit-main">
                          <span className="kgv-hit-label">{n.label}</span>
                          <span className="kgv-hit-sub">{n.heading || (n.text || "").slice(0, 70)}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              )}

              {panel === "help" && (
                <>
                  <div className="kgv-side-title">Tương tác</div>
                  <ul className="kgv-help">
                    <li>Bấm một <b>type</b> trong Ontology để làm nổi các node cùng loại.</li>
                    <li>Bấm một <b>quan hệ</b> để làm nổi triplet của nó.</li>
                    <li><b>Chuột phải</b> vào type hoặc quan hệ để lọc cứng, hoặc ẩn nó khỏi đồ thị.</li>
                    <li>Bấm một node trên đồ thị để mở <b>Chi tiết</b>, rồi xem ngữ cảnh lân cận.</li>
                    <li>Dùng <b>↺</b> trên thanh công cụ để bỏ mọi bộ lọc.</li>
                    <li><b>Group By</b> đổi cách sắp xếp: phân cấp, theo văn bản, theo cấp độ.</li>
                  </ul>
                  <div className="kgv-side-title" style={{ marginTop: 14 }}>Quan hệ</div>
                  <div className="kgv-legend-rows">
                    {ontology.edges.map((oe) => (
                      <div key={`${oe.subject}|${oe.predicate}|${oe.object}`} className="kgv-legend-row">
                        <span className="kgv-leg-line" style={{ background: EDGE_COLOR[oe.predicate] }} />
                        <span>{TYPE_LABEL[oe.subject]} → {TYPE_LABEL[oe.object]}</span>
                        <b>{EDGE_LABEL[oe.predicate] || oe.predicate}</b>
                        <span className="kgv-leg-count">{oe.count}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </>)}

          {/* ── vertical tab strip ─────────────────────────────────────── */}
          <div className="kgv-tabs">
            <button className={panel === "onto" ? "on" : ""} onClick={() => togglePanel("onto")}>Bản đồ mối quan hệ</button>
            <button className={panel === "detail" ? "on" : ""} onClick={() => togglePanel("detail")}>Chi tiết</button>
            <button className={panel === "filter" ? "on" : ""} onClick={() => togglePanel("filter")}>Bộ lọc</button>
            <button className={panel === "help"   ? "on" : ""} onClick={() => togglePanel("help")}>Tương tác</button>
          </div>
        </div>
      </div>
    </>
  );
}
