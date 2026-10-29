"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Script from "next/script";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/* ── palette & vocabulary ────────────────────────────────────────────────── */
const TYPE_COLOR: Record<string, string> = {
  document: "#8b5cf6", article: "#3b82f6", clause: "#10b981", point: "#f59e0b",
};
const DOC_COLOR: Record<string, string> = {
  blld2019: "#3b82f6", blld2012: "#94a3b8", nd145_2020: "#10b981",
};
const EDGE_COLOR: Record<string, string> = {
  contains: "#94a3b8", sibling: "#cbd5e1", reworded: "#f59e0b",
  tightened: "#ef4444", replaces: "#8b5cf6", superseded_by: "#f59e0b",
};
const TYPE_LABEL: Record<string, string> = {
  document: "Văn bản", article: "Điều", clause: "Khoản", point: "Điểm",
};
const EDGE_LABEL: Record<string, string> = {
  contains: "chứa", sibling: "kế tiếp", reworded: "sửa lời",
  tightened: "siết chặt", replaces: "thay thế", superseded_by: "thay thế",
};
const TYPE_RANK: Record<string, number> = {
  document: 0, article: 1, clause: 2, point: 3,
};
const NODE_R: Record<string, number> = {
  document: 17, article: 11, clause: 7, point: 5,
};

/* ── types ───────────────────────────────────────────────────────────────── */
type GNode = {
  id: string; label: string; doc_id: string; doc_type: string;
  level: string; type: string; heading: string; text: string;
  score: number; ghost?: boolean;
  x?: number; y?: number; fx?: number | null; fy?: number | null;
  degree?: number;
};
type GEdge = { source: string | GNode; target: string | GNode; type: string };
type Triplet = { subject?: string; predicate?: string; object?: string };
type OntoEdge = { subject: string; predicate: string; object: string; count: number };
type Menu = { x: number; y: number; kind: "node" | "edge"; node?: string; edge?: OntoEdge };

declare global { interface Window { d3: any } }

const sid = (e: GEdge) => (typeof e.source === "object" ? e.source.id : e.source);
const tid = (e: GEdge) => (typeof e.target === "object" ? e.target.id : e.target);

/* yFiles `matchesValue`: a missing criterion is a wildcard */
const matchesValue = (filter: string | undefined, value: string) => !filter || filter === value;

const tripletKey = (t: Triplet | null) =>
  t ? `${t.subject || "*"}|${t.predicate || "*"}|${t.object || "*"}` : "";

export default function GraphPage() {
  const svgRef  = useRef<SVGSVGElement>(null);
  const simRef  = useRef<any>(null);
  const nodeSel = useRef<any>(null);
  const linkSel = useRef<any>(null);

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
  const [layout,          setLayout]          = useState<"organic" | "clusters" | "levels">("organic");
  const [colorBy,         setColorBy]         = useState<"type" | "doc">("type");
  const [menu,            setMenu]            = useState<Menu | null>(null);

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

    const deg: Record<string, number> = {};
    edges.forEach((e) => { deg[sid(e)] = (deg[sid(e)] || 0) + 1; deg[tid(e)] = (deg[tid(e)] || 0) + 1; });
    nodes.forEach((n) => { n.degree = deg[n.id] || 0; });

    const radius = (n: GNode) => (NODE_R[n.type] || 7) + Math.log1p(n.degree || 0) * 1.1;
    const color  = (n: GNode) =>
      colorBy === "type" ? (TYPE_COLOR[n.type] || "#64748b") : (DOC_COLOR[n.doc_id] || "#64748b");

    const g = svg.append("g");
    svg.call(d3.zoom().scaleExtent([0.08, 6]).on("zoom", (ev: any) => g.attr("transform", ev.transform)));

    const defs = svg.append("defs");
    Object.entries(EDGE_COLOR).forEach(([t, c]) => {
      defs.append("marker").attr("id", `ar-${t}`)
        .attr("markerWidth", 7).attr("markerHeight", 7)
        .attr("refX", 15).attr("refY", 3.5).attr("orient", "auto")
        .append("path").attr("d", "M0,0 L0,7 L7,3.5 z").attr("fill", c).attr("opacity", 0.85);
    });

    const link = g.append("g").selectAll("line").data(edges).enter().append("line")
      .attr("stroke", (e: GEdge) => EDGE_COLOR[e.type] || "#cbd5e1")
      .attr("stroke-width", (e: GEdge) => (e.type === "contains" || e.type === "sibling" ? 1 : 2))
      .attr("stroke-dasharray", (e: GEdge) => (e.type === "sibling" ? "4,3" : null))
      .attr("stroke-opacity", 0.55)
      .attr("marker-end", (e: GEdge) =>
        e.type === "contains" || e.type === "sibling" ? null : `url(#ar-${e.type})`);

    const node = g.append("g").selectAll("g").data(nodes).enter().append("g")
      .attr("cursor", "pointer")
      .on("click", (_: any, d: GNode) => { setSelected(d); setMenu(null); })
      .call(d3.drag()
        .on("start", (ev: any, d: GNode) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag",  (ev: any, d: GNode) => { d.fx = ev.x; d.fy = ev.y; })
        .on("end",   (ev: any, d: GNode) => {
          if (!ev.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = layout === "levels" ? tierY(d) : null;   // keep the tier after a drag
        }));

    node.append("circle")
      .attr("r", radius).attr("fill", color)
      .attr("fill-opacity", 0.88).attr("stroke", "#fff").attr("stroke-width", 1.5);
    node.append("title").text((d: GNode) => `${TYPE_LABEL[d.type] || d.type} · ${d.heading || d.label}`);
    node.append("text")
      .attr("dy", "0.35em").attr("x", (d: GNode) => radius(d) + 4)
      .attr("font-size", (d: GNode) => (d.type === "document" ? "12px" : "10px"))
      .attr("font-weight", (d: GNode) => (d.type === "document" ? "700" : "400"))
      .attr("fill", "var(--foreground,#1e293b)").attr("pointer-events", "none")
      .text((d: GNode) => (d.label.length > 24 ? d.label.slice(0, 24) + "…" : d.label));

    nodes.forEach((n) => { n.fx = null; n.fy = null; });

    // tier mode pins Y per level so the hierarchy stays legible
    const ranks = [...new Set(nodes.map((n) => TYPE_RANK[n.type] ?? 9))].sort((a, b) => a - b);
    const tierY = (d: GNode) => H * ((ranks.indexOf(TYPE_RANK[d.type] ?? 9) + 1) / (ranks.length + 1));
    if (layout === "levels") nodes.forEach((n) => { n.fy = tierY(n); });

    const sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d: GNode) => d.id)
        .distance((e: GEdge) => (e.type === "contains" ? 55 : 95))
        .strength(layout === "levels" ? 0.15 : 1))
      .force("charge", d3.forceManyBody().strength(layout === "organic" ? -260 : -140))
      .force("collide", d3.forceCollide((d: GNode) => radius(d) + 4));

    if (layout === "clusters") {
      const docs = [...new Set(nodes.map((n) => n.doc_id))].sort();
      const cx = (d: GNode) => W * ((docs.indexOf(d.doc_id) + 1) / (docs.length + 1));
      sim.force("x", d3.forceX(cx).strength(0.45))
         .force("y", d3.forceY(H / 2).strength(0.05));
    } else if (layout === "levels") {
      sim.force("x", d3.forceX(W / 2).strength(0.02));
    } else {
      sim.force("center", d3.forceCenter(W / 2, H / 2));
    }

    sim.on("tick", () => {
      link.attr("x1", (e: any) => e.source.x).attr("y1", (e: any) => e.source.y)
          .attr("x2", (e: any) => e.target.x).attr("y2", (e: any) => e.target.y);
      node.attr("transform", (d: GNode) => `translate(${d.x},${d.y})`);
    });

    simRef.current = sim; nodeSel.current = node; linkSel.current = link;
    return () => sim.stop();
  }, [view, layout, colorBy, d3Ready]);

  /* ── fade pass: highlight never re-lays-out, it only dims (yFiles fadeOut) ─ */
  useEffect(() => {
    if (!nodeSel.current || !linkSel.current) return;
    if (!highlight) {
      nodeSel.current.attr("opacity", 1);
      linkSel.current.attr("stroke-opacity", 0.55);
      return;
    }
    const { keepN } = matchSet(highlight, view.nodes, view.edges as GEdge[]);
    nodeSel.current.attr("opacity", (d: GNode) => (keepN.has(d.id) ? 1 : 0.08));
    linkSel.current.attr("stroke-opacity", (e: GEdge) => (edgeMatches(e, highlight) ? 0.95 : 0.04));
  }, [highlight, view, edgeMatches, matchSet]);

  /* ── ontology panel layout: deterministic tiers, no jitter ─────────────── */
  const ontoLayout = useMemo(() => {
    const ranks = [...new Set(ontology.types.map((t) => TYPE_RANK[t] ?? 9))].sort((a, b) => a - b);
    const W = 250, rowH = 58, padTop = 24;
    const pos: Record<string, { x: number; y: number }> = {};
    ranks.forEach((r, ri) => {
      const row = ontology.types.filter((t) => (TYPE_RANK[t] ?? 9) === r);
      // a lone type sits left of centre so its self-loops have room on the right
      row.forEach((t, i) => {
        pos[t] = {
          x: row.length === 1 ? 62 : W * ((i + 1) / (row.length + 1)),
          y: padTop + ri * rowH,
        };
      });
    });
    return { pos, width: W, height: padTop + Math.max(ranks.length - 1, 0) * rowH + 40 };
  }, [ontology.types]);

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

  const focusNode = focusId ? raw.nodes.find((n) => n.id === focusId) : null;

  return (
    <>
      <Script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"
        strategy="afterInteractive" onLoad={() => setD3Ready(true)} />

      <div className="kgv-shell">
        {/* ── top bar ───────────────────────────────────────────────────── */}
        <div className="kgv-topbar">
          <Link href="/" className="kgv-back">← Chat</Link>
          <span className="kgv-title">Knowledge Graph · Luật Lao động</span>

          <form className="kgv-search" onSubmit={(e) => { e.preventDefault(); setQuery(input.trim()); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Tìm kiếm điều luật…" />
            <button type="submit" disabled={loading}>{loading ? "…" : "Tra cứu"}</button>
          </form>

          <label className="kgv-group-label">Bố cục</label>
          <select className="kgv-select" value={layout} onChange={(e) => setLayout(e.target.value as any)}>
            <option value="organic">Tự nhiên</option>
            <option value="clusters">Cụm theo văn bản</option>
            <option value="levels">Tầng theo cấp độ</option>
          </select>

          <label className="kgv-group-label">Màu</label>
          <select className="kgv-select" value={colorBy} onChange={(e) => setColorBy(e.target.value as any)}>
            <option value="type">Theo type</option>
            <option value="doc">Theo văn bản</option>
          </select>

          <button className="kgv-reset-btn" onClick={resetAll} disabled={!activeFilter}>↺ Đặt lại</button>
        </div>

        {/* ── stat bar ──────────────────────────────────────────────────── */}
        <div className="kgv-statbar">
          <span>Nodes <b>{view.nodes.length}</b> / {raw.nodes.length}</span>
          <span>Edges <b>{view.edges.length}</b> / {raw.edges.length}</span>

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

        <div className="kgv-body">
          <div className="kgv-canvas-wrap">
            {loading && <div className="kgv-loading">Đang tải đồ thị…</div>}
            {!loading && !view.nodes.length && (
              <div className="kgv-loading">Không còn node nào — bộ lọc đang quá chặt.</div>
            )}
            <svg ref={svgRef} className="kgv-svg" />

            {/* ── Interactive Ontology View ─────────────────────────────── */}
            <div className="kgv-onto-panel" onPointerDown={(e) => e.stopPropagation()}>
              <div className="kgv-onto-head">
                <span className="kgv-onto-title">Interactive Ontology View</span>
                <span className="kgv-onto-hint">click = làm nổi · chuột phải = lọc / ẩn</span>
              </div>

              <svg width={ontoLayout.width} height={ontoLayout.height} className="kgv-onto-svg">
                <defs>
                  {Object.entries(EDGE_COLOR).map(([t, c]) => (
                    <marker key={t} id={`oar-${t}`} markerWidth="6" markerHeight="6"
                      refX="13" refY="3" orient="auto">
                      <path d="M0,0 L0,6 L6,3 z" fill={c} />
                    </marker>
                  ))}
                </defs>

                {ontology.edges.map((oe) => {
                  const a = ontoLayout.pos[oe.subject], b = ontoLayout.pos[oe.object];
                  if (!a || !b) return null;
                  const off = hiddenEdgeTypes.has(oe.predicate) ||
                    hiddenNodeTypes.has(oe.subject) || hiddenNodeTypes.has(oe.object);
                  const dim = ontoDim(oe.subject, oe.predicate, oe.object);
                  const c   = EDGE_COLOR[oe.predicate] || "#94a3b8";
                  const key = `${oe.subject}|${oe.predicate}|${oe.object}`;
                  const cls = `kgv-onto-edge${off ? " off" : ""}${dim ? " dim" : ""}`;
                  const tip = `${TYPE_LABEL[oe.subject] || oe.subject} —${EDGE_LABEL[oe.predicate] || oe.predicate}→ ${TYPE_LABEL[oe.object] || oe.object} (${oe.count})`;
                  const onClick = () => { if (!off) { setHighlight({ ...oe }); setMenu(null); } };
                  const onCtx = (ev: React.MouseEvent) => {
                    ev.preventDefault();
                    const r = (ev.currentTarget as SVGGElement).ownerSVGElement!.getBoundingClientRect();
                    setMenu({ x: ev.clientX - r.left, y: ev.clientY - r.top, kind: "edge", edge: oe });
                  };

                  /* same-type relation → self loop on the right of the node */
                  if (oe.subject === oe.object) {
                    const loops = ontology.edges.filter((x) => x.subject === x.object && x.subject === oe.subject);
                    const rad = 13 + loops.indexOf(oe) * 8;
                    const d = `M ${a.x + 8} ${a.y - 9} A ${rad} ${rad} 0 1 1 ${a.x + 8} ${a.y + 9}`;
                    return (
                      <g key={key} className={cls} onClick={onClick} onContextMenu={onCtx}>
                        <path d={d} fill="none" stroke={c} strokeWidth={1.4}
                          strokeDasharray={off ? "3,3" : undefined} markerEnd={`url(#oar-${oe.predicate})`} />
                        <path d={d} fill="none" stroke="transparent" strokeWidth={10} />
                        <text x={a.x + rad + 13} y={a.y + 3} fontSize="9" fill={c}>
                          {EDGE_LABEL[oe.predicate] || oe.predicate}
                        </text>
                        <title>{tip}</title>
                      </g>
                    );
                  }

                  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
                  return (
                    <g key={key} className={cls} onClick={onClick} onContextMenu={onCtx}>
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={c} strokeWidth={1.4}
                        strokeDasharray={off ? "3,3" : undefined} markerEnd={`url(#oar-${oe.predicate})`} />
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={12} />
                      <text x={mx - 7} y={my + 3} fontSize="9" fill={c} textAnchor="end">
                        {EDGE_LABEL[oe.predicate] || oe.predicate}
                      </text>
                      <title>{tip}</title>
                    </g>
                  );
                })}

                {ontology.types.map((t) => {
                  const p = ontoLayout.pos[t]; if (!p) return null;
                  const off = hiddenNodeTypes.has(t);
                  const dim = ontoDim(t);
                  const n = raw.nodes.filter((x) => x.type === t).length;
                  return (
                    <g key={t} className={`kgv-onto-node${off ? " off" : ""}${dim ? " dim" : ""}`}
                       onClick={() => { if (!off) { setHighlight({ subject: t }); setMenu(null); } }}
                       onContextMenu={(ev) => {
                         ev.preventDefault();
                         const r = (ev.currentTarget as SVGGElement).ownerSVGElement!.getBoundingClientRect();
                         setMenu({ x: ev.clientX - r.left, y: ev.clientY - r.top, kind: "node", node: t });
                       }}>
                      <circle cx={p.x} cy={p.y} r={15} fill={TYPE_COLOR[t] || "#64748b"}
                        stroke="#fff" strokeWidth={1.5} strokeDasharray={off ? "3,2" : undefined} />
                      <text x={p.x} y={p.y} dy="0.35em" textAnchor="middle" fontSize="9"
                        fontWeight="600" fill="#fff" pointerEvents="none">
                        {TYPE_LABEL[t] || t}
                      </text>
                      <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize="8"
                        fill="var(--muted-foreground,#94a3b8)" pointerEvents="none">{n}</text>
                      <title>{`${TYPE_LABEL[t] || t} — ${n} node`}</title>
                    </g>
                  );
                })}
              </svg>

              {menu && (
                <div className="kgv-ctxmenu" style={{ left: menu.x, top: menu.y + 28 }}
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
          </div>

          {/* ── context / detail panel ──────────────────────────────────── */}
          {selected && (
            <div className="kgv-ctx">
              <button className="kgv-ctx-close" onClick={() => setSelected(null)}>✕</button>
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
            </div>
          )}
        </div>
      </div>
    </>
  );
}
