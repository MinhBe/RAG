"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Script from "next/script";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/* ── màu theo doc_id ── */
const DOC_COLOR: Record<string, string> = {
  blld2019: "#3b82f6",   // xanh dương
  blld2012: "#94a3b8",   // xám
  nd145_2020: "#10b981", // xanh lá
};
const EDGE_COLOR: Record<string, string> = {
  parent_child: "#94a3b8",
  sibling: "#cbd5e1",
  superseded_by: "#f59e0b",
};

type GNode = {
  id: string; label: string; doc_id: string; level: string;
  heading: string; text: string; score: number; ghost?: boolean;
  x?: number; y?: number; vx?: number; vy?: number; fx?: number | null; fy?: number | null;
};
type GEdge = { source: string | GNode; target: string | GNode; type: string };

declare global {
  interface Window { d3: any }
}

export default function GraphPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [query, setQuery] = useState("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<GNode | null>(null);
  const [d3Ready, setD3Ready] = useState(false);
  const simRef = useRef<any>(null);

  const runGraph = useCallback(async (q: string) => {
    if (!window.d3 || !svgRef.current) return;
    // empty query → fetch all nodes
    setLoading(true);
    setSelected(null);
    try {
      const res = await fetch(`${API_BASE}/api/graph?query=${encodeURIComponent(q)}&top_k=20`);
      const data = await res.json();
      drawGraph(data.nodes as GNode[], data.edges as GEdge[]);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [d3Ready]); // eslint-disable-line

  useEffect(() => {
    if (d3Ready) runGraph(query);
  }, [d3Ready, query]); // eslint-disable-line

  function drawGraph(nodes: GNode[], edges: GEdge[]) {
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const W = svgRef.current!.clientWidth || 900;
    const H = svgRef.current!.clientHeight || 600;

    const zoom = d3.zoom()
      .scaleExtent([0.2, 4])
      .on("zoom", (ev: any) => g.attr("transform", ev.transform));
    svg.call(zoom);

    const g = svg.append("g");

    // defs: arrowhead
    svg.append("defs").append("marker")
      .attr("id", "arrow").attr("markerWidth", 6).attr("markerHeight", 6)
      .attr("refX", 14).attr("refY", 3).attr("orient", "auto")
      .append("path").attr("d", "M0,0 L0,6 L6,3 z")
      .attr("fill", "#f59e0b").attr("opacity", 0.7);

    const link = g.append("g").selectAll("line")
      .data(edges).enter().append("line")
      .attr("stroke", (d: GEdge) => EDGE_COLOR[(d as any).type] || "#cbd5e1")
      .attr("stroke-width", (d: GEdge) => (d as any).type === "superseded_by" ? 2 : 1)
      .attr("stroke-opacity", 0.7)
      .attr("marker-end", (d: GEdge) => (d as any).type === "superseded_by" ? "url(#arrow)" : "");

    const node = g.append("g").selectAll("g")
      .data(nodes).enter().append("g")
      .attr("cursor", "pointer")
      .on("click", (_: any, d: GNode) => setSelected(d))
      .call(
        d3.drag()
          .on("start", (ev: any, d: GNode) => {
            if (!ev.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
          })
          .on("drag", (ev: any, d: GNode) => { d.fx = ev.x; d.fy = ev.y; })
          .on("end", (ev: any, d: GNode) => {
            if (!ev.active) sim.alphaTarget(0);
            d.fx = null; d.fy = null;
          })
      );

    node.append("circle")
      .attr("r", (d: GNode) => d.level === "article" ? 14 : d.level === "clause" ? 10 : 7)
      .attr("fill", (d: GNode) => DOC_COLOR[d.doc_id] || "#6366f1")
      .attr("fill-opacity", (d: GNode) => d.ghost ? 0.4 : 0.85)
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5);

    node.append("text")
      .attr("dy", "0.35em")
      .attr("x", (d: GNode) => (d.level === "article" ? 14 : 10) + 5)
      .attr("font-size", "11px")
      .attr("fill", "var(--foreground, #1e293b)")
      .text((d: GNode) => {
        const lbl = d.label || d.id;
        return lbl.length > 28 ? lbl.slice(0, 28) + "…" : lbl;
      });

    const sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d: GNode) => d.id).distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collide", d3.forceCollide(30))
      .on("tick", () => {
        link
          .attr("x1", (d: any) => d.source.x)
          .attr("y1", (d: any) => d.source.y)
          .attr("x2", (d: any) => d.target.x)
          .attr("y2", (d: any) => d.target.y);
        node.attr("transform", (d: GNode) => `translate(${d.x},${d.y})`);
      });

    simRef.current = sim;
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(input.trim()); // allow empty — shows all nodes
  }

  return (
    <>
      <Script
        src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"
        strategy="afterInteractive"
        onLoad={() => setD3Ready(true)}
      />

      <div className="graph-shell">
        {/* Header */}
        <div className="graph-header">
          <Link href="/" className="graph-back">← Chat</Link>
          <span className="graph-title">Knowledge Graph · Luật Lao động</span>
          <form onSubmit={handleSearch} className="graph-search">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Nhập từ khóa pháp lý…"
            />
            <button type="submit" disabled={loading}>
              {loading ? "…" : "Tra cứu"}
            </button>
          </form>
        </div>

        {/* Legend */}
        <div className="graph-legend">
          {Object.entries(DOC_COLOR).map(([doc, color]) => (
            <span key={doc} className="legend-item">
              <span className="legend-dot" style={{ background: color }} />
              {doc}
            </span>
          ))}
          <span className="legend-item">
            <span className="legend-line amber" />
            thay thế (BLLĐ 2012→2019)
          </span>
          <span className="legend-item">
            <span className="legend-line gray" />
            phân cấp / anh em
          </span>
        </div>

        <div className="graph-body">
          {/* Graph SVG */}
          <div className="graph-canvas-wrap">
            {loading && <div className="graph-loading">Đang tải đồ thị…</div>}
            <svg ref={svgRef} className="graph-svg" />
          </div>

          {/* Side panel */}
          {selected && (
            <div className="graph-panel">
              <button className="graph-panel-close" onClick={() => setSelected(null)}>✕</button>
              <div className="gp-doc-badge" style={{ background: DOC_COLOR[selected.doc_id] || "#6366f1" }}>
                {selected.doc_id}
              </div>
              <div className="gp-id">{selected.id}</div>
              <div className="gp-heading">{selected.heading || selected.label}</div>
              <div className="gp-text">{selected.text || "Không có nội dung."}</div>
              {selected.score > 0 && (
                <div className="gp-score">Điểm liên quan: {selected.score}</div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
