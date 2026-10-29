import Link from "next/link";

import { IconDash, IconGraph, IconPlus } from "@/components/chat/icons";
import type { Conversation } from "@/lib/chat/types";

export default function Sidebar({ open, convos, activeId, onNew, onOpen, onDelete }: {
  open: boolean;
  convos: Conversation[];
  activeId: string | null;
  onNew: () => void;
  onOpen: (c: Conversation) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <aside className={`sidebar ${open ? "" : "closed"}`}>
      <div className="brand">
        <div className="logo">L</div>
        <div>
          <div className="name">Trợ lý Luật Lao động</div>
          <div className="sub">Hỏi đáp có trích dẫn</div>
        </div>
      </div>

      <button className="new-chat" onClick={onNew}>
        <IconPlus /> Cuộc trò chuyện mới
      </button>

      <div className="side-quick-links">
        <Link href="/graph" className="side-quick-btn">
          <IconGraph /> Knowledge Graph
        </Link>
        <Link href="/dashboard" className="side-quick-btn">
          <IconDash /> Dashboard
        </Link>
      </div>

      <div className="side-label">Gần đây</div>
      <div className="thread-list">
        {convos.length === 0 && <div className="thread-empty">Chưa có cuộc trò chuyện nào.</div>}
        {convos.map((c) => (
          <div key={c.id} className={`thread-item ${c.id === activeId ? "active" : ""}`} title={c.title}>
            <span className="thread-title" onClick={() => onOpen(c)}>{c.title}</span>
            <button
              className="thread-del"
              title="Xóa cuộc trò chuyện"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
            >···</button>
          </div>
        ))}
      </div>

      <div className="side-foot">
        Nguồn: BLLĐ 2019 · 2012 · NĐ 145/2020 · án lệ lao động. Câu trả lời kèm trích dẫn Điều–Khoản.
      </div>
    </aside>
  );
}
