"use client";

/* Trang /pv: thư viện câu hỏi phỏng vấn. Không có link nào trỏ tới, chỉ mở khi gõ
   /pv trong ô chat hoặc gõ thẳng địa chỉ. Nội dung lấy từ GET /api/pv. */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { PARTS, type PvItem, type PvLibrary } from "@/lib/pv/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const norm = (s: string) =>
  s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d");

function Card({ item, layerName, practice, open, onToggle }: {
  item: PvItem; layerName: string; practice: boolean; open: boolean; onToggle: () => void;
}) {
  const shown = !practice || open;
  return (
    <article className="pv-card" id={item.id}>
      <header className="pv-card-head">
        <span className="pv-id">{item.id}</span>
        <span className="pv-badge">{layerName}</span>
        {item.source === "bổ sung" && <span className="pv-badge pv-badge-new">bổ sung</span>}
      </header>
      <h3 className="pv-title">{item.title}</h3>
      <div className="pv-ask">
        <div className="pv-label">Sếp hỏi</div>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.question}</ReactMarkdown>
      </div>
      {practice && (
        <button className="pv-reveal" onClick={onToggle}>
          {open ? "Ẩn gợi ý" : "Tự trả lời xong, xem gợi ý"}
        </button>
      )}
      {shown && PARTS.map(({ key, label }) => (
        <section key={key} className="pv-part">
          <div className="pv-label">{label}</div>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{item[key] as string}</ReactMarkdown>
        </section>
      ))}
      {shown && item.files.length > 0 && (
        <div className="pv-files">Code liên quan: {item.files.map((f) => <code key={f}>{f}</code>)}</div>
      )}
    </article>
  );
}

export default function PvPage() {
  const [lib, setLib] = useState<PvLibrary | null>(null);
  const [error, setError] = useState("");
  const [group, setGroup] = useState("all");
  const [layer, setLayer] = useState("all");
  const [query, setQuery] = useState("");
  const [practice, setPractice] = useState(true);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/pv`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setLib)
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  const items = useMemo(() => {
    if (!lib) return [];
    const q = norm(query.trim());
    return lib.groups
      .filter((g) => group === "all" || g.group === group)
      .flatMap((g) => g.items)
      .filter((it) => layer === "all" || it.layer === layer)
      .filter((it) => !q || norm(`${it.id} ${it.title} ${it.question} ${it.tags.join(" ")}`).includes(q));
  }, [lib, group, layer, query]);

  const visible = focus ? items.filter((it) => it.id === focus) : items;

  const toggle = (id: string) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const randomOne = () => {
    if (!items.length) return;
    const pick = items[Math.floor(Math.random() * items.length)];
    setOpen((prev) => { const next = new Set(prev); next.delete(pick.id); return next; });
    setFocus(pick.id);
  };

  const total = lib?.groups.reduce((n, g) => n + g.items.length, 0) ?? 0;

  return (
    <div className="pv-shell">
      <header className="header">
        <Link href="/" className="graph-nav-btn" title="Về trang chat">←</Link>
        <span className="title">Luyện phỏng vấn</span>
        {lib && <span className="pv-count">{total} câu</span>}
      </header>

      <div className="pv-body">
        <div className="pv-toolbar">
          <input className="pv-search" value={query} placeholder="Tìm theo từ khóa, mã câu, tag…"
            onChange={(e) => { setQuery(e.target.value); setFocus(null); }} />
          <select className="pv-select" value={layer} onChange={(e) => { setLayer(e.target.value); setFocus(null); }}>
            <option value="all">Mọi lớp câu hỏi</option>
            {lib && Object.entries(lib.layers).map(([k, v]) => <option key={k} value={k}>{k}. {v}</option>)}
          </select>
          <label className="pv-toggle">
            <input type="checkbox" checked={practice} onChange={(e) => setPractice(e.target.checked)} />
            Tự luyện (ẩn gợi ý)
          </label>
          <button className="pv-btn" onClick={randomOne} disabled={!items.length}>Câu ngẫu nhiên</button>
          {focus && <button className="pv-btn pv-btn-ghost" onClick={() => setFocus(null)}>Xem tất cả</button>}
        </div>

        {lib && (
          <div className="pv-chips">
            <button className={`pv-chip ${group === "all" ? "on" : ""}`}
              onClick={() => { setGroup("all"); setFocus(null); }}>Tất cả</button>
            {lib.groups.map((g) => (
              <button key={g.group} className={`pv-chip ${group === g.group ? "on" : ""}`}
                onClick={() => { setGroup(g.group); setFocus(null); }}>
                {g.title} <span className="pv-chip-n">{g.items.length}</span>
              </button>
            ))}
          </div>
        )}

        {error && <div className="pv-empty">Không tải được thư viện câu hỏi ({error}). Kiểm tra API đang chạy.</div>}
        {!lib && !error && <div className="pv-empty">Đang tải…</div>}
        {lib && !visible.length && <div className="pv-empty">Không có câu nào khớp bộ lọc.</div>}

        <div className="pv-list">
          {lib && visible.map((it) => (
            <Card key={it.id} item={it} layerName={lib.layers[it.layer] ?? it.layer} practice={practice}
              open={open.has(it.id)} onToggle={() => toggle(it.id)} />
          ))}
        </div>
      </div>
    </div>
  );
}
