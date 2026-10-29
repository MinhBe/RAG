"use client";

/* Thanh công cụ nổi trên đồ thị: zoom, đặt lại bộ lọc, Group By, màu, tra cứu. */
import { useState } from "react";

import type { ColorBy, GroupBy } from "@/lib/graph/model";

type Props = {
  activeFilter: boolean;
  groupBy: GroupBy;
  colorBy: ColorBy;
  onZoom: (factor: number) => void;
  onFit: () => void;
  onReset: () => void;
  onGroupBy: (g: GroupBy) => void;
  onColorBy: (c: ColorBy) => void;
  onSearch: (q: string) => void;
};

export default function GraphToolbar(p: Props) {
  const [input, setInput] = useState("");
  return (
    <div className="kgv-toolbar">
      <button title="Thu nhỏ" onClick={() => p.onZoom(1 / 1.4)}>−</button>
      <button title="Phóng to" onClick={() => p.onZoom(1.4)}>+</button>
      <button title="Vừa khung" onClick={p.onFit}>⤢</button>
      <button title="Đặt lại bộ lọc" onClick={p.onReset} disabled={!p.activeFilter}>↺</button>
      <span className="kgv-tb-sep" />
      <label>Group By</label>
      <select value={p.groupBy} onChange={(e) => p.onGroupBy(e.target.value as GroupBy)}>
        <option value="radial">Chương</option>
        <option value="doc">Văn bản</option>
        <option value="level">Cấp độ</option>
        <option value="organic">Tự nhiên</option>
      </select>
      <select value={p.colorBy} onChange={(e) => p.onColorBy(e.target.value as ColorBy)}>
        <option value="type">Màu: type</option>
        <option value="doc">Màu: văn bản</option>
      </select>
      <span className="kgv-tb-sep" />
      <form onSubmit={(e) => { e.preventDefault(); p.onSearch(input.trim()); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Tra cứu điều luật…" />
      </form>
    </div>
  );
}
