/* Dải chip cho mọi bộ lọc đang bật; bấm ✕ để gỡ từng cái. */
import { EDGE_LABEL, edgeLabel, type Triplet, TYPE_LABEL, typeLabel } from "@/lib/graph/model";

type Props = {
  filterTriplet: Triplet | null;
  highlight: Triplet | null;
  hiddenNodeTypes: Set<string>;
  hiddenEdgeTypes: Set<string>;
  focusLabel: string | null;
  onClearFilter: () => void;
  onClearHighlight: () => void;
  onToggleNodeType: (t: string) => void;
  onToggleEdgeType: (p: string) => void;
  onClearFocus: () => void;
};

export default function FilterChips(p: Props) {
  return (
    <div className="kgv-statbar">
      {p.filterTriplet && (
        <span className="kgv-chip kgv-chip-filter">
          Lọc: {typeLabel(p.filterTriplet.subject)}
          {" —"}{edgeLabel(p.filterTriplet.predicate)}{"→ "}
          {typeLabel(p.filterTriplet.object)}
          <button onClick={p.onClearFilter}>✕</button>
        </span>
      )}
      {p.highlight && (
        <span className="kgv-chip kgv-chip-hl">
          Làm nổi: {typeLabel(p.highlight.subject)}
          {p.highlight.predicate &&
            ` —${edgeLabel(p.highlight.predicate)}→ ${typeLabel(p.highlight.object)}`}
          <button onClick={p.onClearHighlight}>✕</button>
        </span>
      )}
      {[...p.hiddenNodeTypes].map((t) => (
        <span key={t} className="kgv-chip kgv-chip-hidden">
          Ẩn {TYPE_LABEL[t] || t}<button onClick={() => p.onToggleNodeType(t)}>✕</button>
        </span>
      ))}
      {[...p.hiddenEdgeTypes].map((t) => (
        <span key={t} className="kgv-chip kgv-chip-hidden">
          Ẩn “{EDGE_LABEL[t] || t}”<button onClick={() => p.onToggleEdgeType(t)}>✕</button>
        </span>
      ))}
      {p.focusLabel !== null && (
        <span className="kgv-chip kgv-chip-focus">
          Ngữ cảnh: {p.focusLabel}<button onClick={p.onClearFocus}>✕</button>
        </span>
      )}
    </div>
  );
}
