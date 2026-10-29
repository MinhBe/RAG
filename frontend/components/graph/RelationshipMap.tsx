"use client";

/* Bản đồ mối quan hệ (Interactive Ontology View): mỗi type một nút, mỗi triplet
   một cạnh. Bấm để làm nổi, chuột phải để lọc / ẩn; có kính lúp, kéo nền, và
   tay kéo đổi chiều cao. */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  EDGE_LABEL, ONTO_EDGE_COLOR, ONTO_LOOP_DIR, ONTO_R, type OntoEdge, type Ontology,
  ontoDimmed, type Point, tripletKey, type Triplet, TYPE_COLOR, TYPE_LABEL,
} from "@/lib/graph/model";
import { loadNumber, saveNumber, startDrag } from "@/lib/ui/drag";

type Menu = { x: number; y: number; kind: "node" | "edge"; node?: string; edge?: OntoEdge };

type Props = {
  ontology: Ontology;
  positions: Record<string, Point>;
  typeCounts: Record<string, number>;
  hiddenNodeTypes: Set<string>;
  hiddenEdgeTypes: Set<string>;
  filterTriplet: Triplet | null;
  highlight: Triplet | null;
  activeFilter: boolean;
  panelWidth: number;
  onHighlight: (t: Triplet) => void;
  onFilter: (t: Triplet | null) => void;
  onToggleNodeType: (t: string) => void;
  onToggleEdgeType: (p: string) => void;
  onReset: () => void;
};

export default function RelationshipMap(props: Props) {
  const {
    ontology, positions: ontoPos, typeCounts, hiddenNodeTypes, hiddenEdgeTypes,
    filterTriplet, highlight, activeFilter, panelWidth,
    onHighlight, onFilter, onToggleNodeType, onToggleEdgeType, onReset,
  } = props;

  const [menu, setMenu] = useState<Menu | null>(null);
  const [ontoH, setOntoH] = useState(520);
  const [ov, setOv] = useState({ k: 1, x: 0, y: 0 });
  const ontoStageRef = useRef<HTMLDivElement>(null);
  const ontoContentRef = useRef<SVGGElement>(null);
  const userZoomed = useRef(false);

  useEffect(() => {
    // no saved height yet: size the map to the screen, not a fixed guess
    setOntoH(loadNumber("kgv_ontoH") || Math.max(380, Math.min(760, window.innerHeight - 250)));
  }, []);

  // resizing the panel hands control back to auto-fit, so the map grows with it
  useEffect(() => { userZoomed.current = false; }, [panelWidth]);

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

  /* refit on open, on new data, and on resize unless the user zoomed by hand */
  useEffect(() => {
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
  }, [ontology.types, fitOnto, zoomOntoAt]);

  useEffect(() => {
    if (!menu) return;
    // close only on a press outside the menu, so the menu's own buttons still fire
    const close = (ev: PointerEvent) => {
      if (!(ev.target as Element | null)?.closest?.(".kgv-ctxmenu")) setMenu(null);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [menu]);

  const openMenu = (ev: React.MouseEvent, m: Omit<Menu, "x" | "y">) => {
    ev.preventDefault();
    const r = (ev.currentTarget as Element).closest(".kgv-onto-block")!.getBoundingClientRect();
    setMenu({ x: ev.clientX - r.left, y: ev.clientY - r.top, ...m });
  };

  return (
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
          <button title="Đặt lại bộ lọc" onClick={onReset} disabled={!activeFilter}>↺</button>
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
              {ontology.edges.map((oe) => (
                <MapEdge key={`${oe.subject}|${oe.predicate}|${oe.object}`} oe={oe} ontology={ontology} pos={ontoPos}
                  off={hiddenEdgeTypes.has(oe.predicate) || hiddenNodeTypes.has(oe.subject) || hiddenNodeTypes.has(oe.object)}
                  dim={ontoDimmed(filterTriplet, oe.subject, oe.predicate, oe.object)}
                  hl={!!highlight?.predicate && tripletKey(highlight) === tripletKey(oe)}
                  onClick={() => { onHighlight({ ...oe }); setMenu(null); }}
                  onContextMenu={(ev) => openMenu(ev, { kind: "edge", edge: oe })} />
              ))}

              {ontology.types.map((t) => (
                <MapNode key={t} type={t} p={ontoPos[t]} count={typeCounts[t] || 0}
                  off={hiddenNodeTypes.has(t)} dim={ontoDimmed(filterTriplet, t)}
                  hl={!!highlight && !highlight.predicate && highlight.subject === t}
                  onClick={() => { onHighlight({ subject: t }); setMenu(null); }}
                  onContextMenu={(ev) => openMenu(ev, { kind: "node", node: t })} />
              ))}
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
          }, () => saveNumber("kgv_ontoH", h));
        }} />

      {menu && (
        <div className="kgv-ctxmenu" style={{ left: Math.max(8, Math.min(menu.x, panelWidth - 230)), top: menu.y + 6 }}
             onPointerDown={(e) => e.stopPropagation()}>
          {menu.kind === "edge" && menu.edge && (() => {
            const oe = menu.edge;
            const isFiltered = tripletKey(filterTriplet) === tripletKey(oe);
            const blocked = hiddenEdgeTypes.has(oe.predicate) ||
              hiddenNodeTypes.has(oe.subject) || hiddenNodeTypes.has(oe.object);
            return (
              <>
                <button disabled={blocked}
                  onClick={() => { onFilter(isFiltered ? null : { ...oe }); setMenu(null); }}>
                  {isFiltered ? "Bỏ lọc triplet" : "Lọc triplet này"}
                </button>
                <button onClick={() => { onToggleEdgeType(oe.predicate); setMenu(null); }}>
                  {hiddenEdgeTypes.has(oe.predicate) ? "Hiện" : "Ẩn"} quan hệ “{EDGE_LABEL[oe.predicate] || oe.predicate}”
                </button>
              </>
            );
          })()}
          {menu.kind === "node" && menu.node && (
            <>
              <button onClick={() => { onFilter({ subject: menu.node }); setMenu(null); }}>
                Lọc chỉ “{TYPE_LABEL[menu.node] || menu.node}”
              </button>
              <button onClick={() => { onToggleNodeType(menu.node!); setMenu(null); }}>
                {hiddenNodeTypes.has(menu.node) ? "Hiện" : "Ẩn"} type “{TYPE_LABEL[menu.node] || menu.node}”
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ── one relation (triplet) on the map ───────────────────────────────────── */
function MapEdge({ oe, ontology, pos, off, dim, hl, onClick, onContextMenu }: {
  oe: OntoEdge; ontology: Ontology; pos: Record<string, Point>;
  off: boolean; dim: boolean; hl: boolean;
  onClick: () => void; onContextMenu: (ev: React.MouseEvent) => void;
}) {
  const a = pos[oe.subject], b = pos[oe.object];
  if (!a || !b) return null;
  const R = ONTO_R;
  const c = ONTO_EDGE_COLOR[oe.predicate] || "#94a3b8";
  const cls = `kgv-onto-edge${off ? " off" : ""}${dim ? " dim" : ""}${hl ? " hl" : ""}`;
  const label = EDGE_LABEL[oe.predicate] || oe.predicate;
  const tip = `${TYPE_LABEL[oe.subject] || oe.subject} —${label}→ ${TYPE_LABEL[oe.object] || oe.object} (${oe.count})`;

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
    const A = pos[pair[0]], B = pos[pair[1]];
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
    <g className={cls} onClick={() => { if (!off) onClick(); }} onContextMenu={onContextMenu}>
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
}

/* ── one type on the map ─────────────────────────────────────────────────── */
function MapNode({ type: t, p, count: n, off, dim, hl, onClick, onContextMenu }: {
  type: string; p: Point | undefined; count: number; off: boolean; dim: boolean; hl: boolean;
  onClick: () => void; onContextMenu: (ev: React.MouseEvent) => void;
}) {
  if (!p) return null;
  const name = TYPE_LABEL[t] || t;
  const fs = 15, pw = name.length * fs * 0.6 + 14, ph = fs + 10;
  return (
    <g className={`kgv-onto-node${off ? " off" : ""}${dim ? " dim" : ""}${hl ? " hl" : ""}`}
       onClick={() => { if (!off) onClick(); }} onContextMenu={onContextMenu}>
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
}
