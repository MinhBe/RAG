/* Nội dung các tab bên phải ngoài bản đồ: Chi tiết, Bộ lọc, Tương tác. */
import {
  DOC_COLOR, EDGE_COLOR, EDGE_LABEL, type GNode, type OntoEdge, TYPE_COLOR, TYPE_LABEL,
} from "@/lib/graph/model";

export function DetailPanel({ selected, focused, onToggleFocus }: {
  selected: GNode | null; focused: boolean; onToggleFocus: () => void;
}) {
  if (!selected) {
    return (
      <>
        <div className="kgv-side-title">Chi tiết</div>
        <p className="kgv-side-empty">Chọn một node trên đồ thị để xem nội dung.</p>
      </>
    );
  }
  return (
    <>
      <div className="kgv-side-title">Chi tiết</div>
      <div className="kgv-ctx-badges">
        <span className="kgv-ctx-badge" style={{ background: TYPE_COLOR[selected.type] || "#64748b" }}>
          {TYPE_LABEL[selected.type] || selected.type}
        </span>
        <span className="kgv-ctx-badge" style={{ background: DOC_COLOR[selected.doc_id] || "#64748b" }}>
          {selected.doc_name || selected.doc_id}
        </span>
      </div>
      <div className="kgv-ctx-id">{selected.id}</div>
      <div className="kgv-ctx-heading">{selected.heading || selected.label}</div>
      <div className="kgv-ctx-text">{selected.text || "Không có nội dung."}</div>
      {selected.score > 0 && <div className="kgv-ctx-score">Độ liên quan: {selected.score}</div>}
      <button className={`kgv-ctx-focus-btn ${focused ? "active" : ""}`} onClick={onToggleFocus}>
        {focused ? "↩ Bỏ ngữ cảnh" : "🔍 Xem ngữ cảnh node này"}
      </button>
    </>
  );
}

export function LookupPanel({ types, query, onQuery, type, onType, hits, onPick }: {
  types: string[];
  query: string; onQuery: (q: string) => void;
  type: string; onType: (t: string) => void;
  hits: GNode[]; onPick: (n: GNode) => void;
}) {
  return (
    <>
      <div className="kgv-side-title">Bộ lọc</div>
      <input className="kgv-side-input" value={query} autoFocus
        onChange={(e) => onQuery(e.target.value)}
        placeholder="Tra từ khóa trong nội dung…" />
      <div className="kgv-side-types">
        <button className={type === "" ? "on" : ""} onClick={() => onType("")}>Tất cả</button>
        {types.map((t) => (
          <button key={t} className={type === t ? "on" : ""}
            style={type === t ? { background: TYPE_COLOR[t], borderColor: TYPE_COLOR[t] } : undefined}
            onClick={() => onType(type === t ? "" : t)}>
            {TYPE_LABEL[t] || t}
          </button>
        ))}
      </div>
      <div className="kgv-side-count">
        {query || type ? `${hits.length} kết quả` : "Nhập từ khóa hoặc chọn type."}
      </div>
      <div className="kgv-side-list">
        {hits.map((n) => (
          <button key={n.id} className="kgv-hit" onClick={() => onPick(n)}>
            <span className="kgv-hit-dot" style={{ background: TYPE_COLOR[n.type] }} />
            <span className="kgv-hit-main">
              <span className="kgv-hit-label">{n.label}</span>
              <span className="kgv-hit-sub">{n.heading || (n.text || "").slice(0, 70)}</span>
            </span>
          </button>
        ))}
      </div>
    </>
  );
}

export function HelpPanel({ relations }: { relations: OntoEdge[] }) {
  return (
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
        {relations.map((oe) => (
          <div key={`${oe.subject}|${oe.predicate}|${oe.object}`} className="kgv-legend-row">
            <span className="kgv-leg-line" style={{ background: EDGE_COLOR[oe.predicate] }} />
            <span>{TYPE_LABEL[oe.subject]} → {TYPE_LABEL[oe.object]}</span>
            <b>{EDGE_LABEL[oe.predicate] || oe.predicate}</b>
            <span className="kgv-leg-count">{oe.count}</span>
          </div>
        ))}
      </div>
    </>
  );
}
