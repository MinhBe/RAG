/* Vẽ đồ thị chính bằng d3 (nạp từ CDN, không có kiểu nên dùng any).

   Bố cục theo demo yFiles: chỉ hub (Văn bản, Chương) tham gia mô phỏng lực,
   mọi node khác xếp nan quạt quanh cha với bán kính đủ cho cả cây con. */
import {
  type ColorBy, DOC_COLOR, EDGE_COLOR, edgeMatches, type GEdge, type GNode, type GraphData,
  type GroupBy, HUB_TYPES, matchSet, NODE_R, type Ontology, sid, tid, type Triplet,
  TYPE_COLOR, TYPE_LABEL, TYPE_RANK,
} from "@/lib/graph/model";

declare global { interface Window { d3: any } }

export type ForceGraph = { node: any; link: any; zoom: any; svg: any; stop: () => void };

const spoke = (e: GEdge) => e.type === "contains" || e.type === "sibling";
const restingEdgeOpacity = (e: GEdge) => (spoke(e) ? 0.35 : 0.7);

export function drawForceGraph(
  svgEl: SVGSVGElement,
  view: GraphData,
  opts: { groupBy: GroupBy; colorBy: ColorBy; onNodeClick: (n: GNode) => void },
): ForceGraph | null {
  const { groupBy, colorBy, onNodeClick } = opts;
  const d3 = window.d3;
  const svg = d3.select(svgEl);
  svg.selectAll("*").remove();

  const nodes: GNode[] = view.nodes;
  const edges: GEdge[] = view.edges;
  if (!nodes.length) return null;

  const W = svgEl.clientWidth || 900;
  const H = svgEl.clientHeight || 600;
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
  const parentOf = new Map<string, string>();
  const kidsOf = new Map<string, GNode[]>();
  edges.forEach((e) => {
    if (e.type !== "contains") return;
    const p = byId.get(sid(e)), c = byId.get(tid(e));
    if (!p || !c) return;
    parentOf.set(c.id, p.id);
    (kidsOf.get(p.id) || kidsOf.set(p.id, []).get(p.id)!).push(c);
  });

  const radialMode = groupBy === "radial" || groupBy === "doc";
  // only nodes that are not fanned out around a parent take part in the simulation
  let simNodes = radialMode
    ? nodes.filter((n) => HUB_TYPES.has(n.type) || !parentOf.has(n.id))
    : nodes;

  /* A node linked only to fanned nodes (the interview graph's topics and layers)
     has no edge inside the simulation, so nothing holds it and it drifts alone.
     Take it out and park it at the centre of the nodes it links instead. */
  const anchors = new Map<string, GNode[]>();
  if (radialMode) {
    const inSim = new Set(simNodes.map((n) => n.id));
    const linked = new Set<string>();
    edges.forEach((e) => {
      if (inSim.has(sid(e)) && inSim.has(tid(e))) { linked.add(sid(e)); linked.add(tid(e)); }
    });
    simNodes.forEach((n) => {
      if (HUB_TYPES.has(n.type) || linked.has(n.id)) return;
      const nb = edges
        .map((e) => (sid(e) === n.id ? byId.get(tid(e)) : tid(e) === n.id ? byId.get(sid(e)) : undefined))
        .filter((x): x is GNode => !!x);
      if (nb.length) anchors.set(n.id, nb);
    });
    simNodes = simNodes.filter((n) => !anchors.has(n.id));
  }
  const placeAnchors = () => {
    let i = 0;
    anchors.forEach((nb, id) => {
      const n = byId.get(id)!;
      // small fixed offset so nodes sharing the same neighbours do not stack
      const a = (i++ * 2.4) % (2 * Math.PI);
      n.x = nb.reduce((s, k) => s + (k.x ?? CX), 0) / nb.length + 14 * Math.cos(a);
      n.y = nb.reduce((s, k) => s + (k.y ?? CY), 0) / nb.length + 14 * Math.sin(a);
    });
  };
  const simIds = new Set(simNodes.map((n) => n.id));
  const simEdges = edges.filter((e) => simIds.has(sid(e)) && simIds.has(tid(e)));

  const g = svg.append("g");
  // a zoom or pan by the user (sourceEvent set) stops the automatic fit below
  let userMoved = false;
  const zoom = d3.zoom().scaleExtent([0.05, 8]).on("zoom", (ev: any) => {
    g.attr("transform", ev.transform);
    if (ev.sourceEvent) userMoved = true;
  });
  svg.call(zoom);

  const defs = svg.append("defs");
  Object.entries(EDGE_COLOR).forEach(([t, c]) => {
    defs.append("marker").attr("id", `ar-${t}`)
      .attr("markerWidth", 7).attr("markerHeight", 7)
      .attr("refX", 13).attr("refY", 3.5).attr("orient", "auto")
      .append("path").attr("d", "M0,0 L0,7 L7,3.5 z").attr("fill", c).attr("opacity", 0.9);
  });

  const link = g.append("g").attr("fill", "none")
    .selectAll("path").data(edges).enter().append("path")
    .attr("stroke", (e: GEdge) => EDGE_COLOR[e.type] || "#cbd5e1")
    .attr("stroke-width", (e: GEdge) => (spoke(e) ? 0.7 : 1.8))
    .attr("stroke-dasharray", (e: GEdge) => (e.type === "sibling" ? "3,3" : null))
    .attr("stroke-opacity", restingEdgeOpacity)
    .attr("marker-end", (e: GEdge) => (spoke(e) ? null : `url(#ar-${e.type})`));

  const ranks = [...new Set(nodes.map((n) => TYPE_RANK[n.type] ?? 9))].sort((a, b) => a - b);
  const tierY = (d: GNode) => H * ((ranks.indexOf(TYPE_RANK[d.type] ?? 9) + 1) / (ranks.length + 1));

  // assigned below; the drag handlers only run once it exists
  let sim: any;
  const node = g.append("g").selectAll("g").data(nodes).enter().append("g")
    .attr("cursor", "pointer")
    .on("click", (_: any, d: GNode) => onNodeClick(d))
    .call(d3.drag()
      .on("start", (ev: any, d: GNode) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (ev: any, d: GNode) => { d.fx = ev.x; d.fy = ev.y; })
      .on("end", (ev: any, d: GNode) => {
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

  sim = d3.forceSimulation(simNodes)
    .force("link", d3.forceLink(simEdges).id((d: GNode) => d.id)
      .distance((e: GEdge) => (e.type === "contains" ? 110 : 150))
      .strength(groupBy === "level" ? 0.15 : 0.6))
    .force("charge", d3.forceManyBody().strength(-260).distanceMax(900))
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
  const layoutFans = () => {
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
  };

  const edgePath = (e: GEdge) => {
    const s = e.source as GNode, t = e.target as GNode;
    const sx = s.x ?? 0, sy = s.y ?? 0, tx = t.x ?? 0, ty = t.y ?? 0;
    if (spoke(e)) return `M${sx},${sy}L${tx},${ty}`;
    // bundle long cross-links by bending them toward the centre
    const mx = (sx + tx) / 2, my = (sy + ty) / 2;
    return `M${sx},${sy}Q${mx + (CX - mx) * 0.4},${my + (CY - my) * 0.4} ${tx},${ty}`;
  };

  /* The fans of a large graph reach far past the viewport, so without a fit
     most of it sits off-screen and the canvas looks empty. Fit once the layout
     has spread out, and again when it settles, unless the user has moved it. */
  const autoFit = () => {
    if (userMoved) return;
    const t = fitTransform(svgEl, g.node());
    if (t) svg.call(zoom.transform, t);
  };
  let ticks = 0;
  sim.on("tick", () => {
    if (radialMode) { layoutFans(); placeAnchors(); }
    link.attr("d", edgePath);
    node.attr("transform", (d: GNode) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    if (++ticks === 30) autoFit();
  });
  sim.on("end", autoFit);

  return { node, link, zoom, svg, stop: () => sim.stop() };
}

/* highlight never re-lays-out, it only dims (yFiles fadeOut) */
export function applyHighlight(fg: ForceGraph | null, ontology: Ontology, view: GraphData, highlight: Triplet | null) {
  if (!fg) return;
  if (!highlight) {
    fg.node.attr("opacity", 1);
    fg.link.attr("stroke-opacity", restingEdgeOpacity);
    return;
  }
  const { keepN } = matchSet(ontology, highlight, view.nodes, view.edges);
  fg.node.attr("opacity", (d: GNode) => (keepN.has(d.id) ? 1 : 0.07));
  fg.link.attr("stroke-opacity", (e: GEdge) => (edgeMatches(ontology, e, highlight) ? 0.95 : 0.03));
}

export function zoomBy(fg: ForceGraph | null, k: number) {
  fg?.svg.transition().duration(220).call(fg.zoom.scaleBy, k);
}

/* zoom transform that fits everything inside `g` into the svg, or null when empty */
function fitTransform(svgEl: SVGSVGElement, g: SVGGElement | null) {
  if (!g) return null;
  const b = g.getBBox();
  if (!b.width || !b.height) return null;
  const k = Math.min(svgEl.clientWidth / b.width, svgEl.clientHeight / b.height) * 0.9;
  const tx = svgEl.clientWidth / 2 - k * (b.x + b.width / 2);
  const ty = svgEl.clientHeight / 2 - k * (b.y + b.height / 2);
  return window.d3.zoomIdentity.translate(tx, ty).scale(k);
}

export function zoomFit(fg: ForceGraph | null, svgEl: SVGSVGElement | null) {
  if (!fg || !svgEl) return;
  const t = fitTransform(svgEl, svgEl.querySelector("g"));
  if (t) fg.svg.transition().duration(350).call(fg.zoom.transform, t);
}
