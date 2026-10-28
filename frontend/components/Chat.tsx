"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

const REFUSAL = "Không đủ căn cứ trong kho văn bản để trả lời chắc chắn câu này.";

type Citation = { n?: number; node_id: string; display?: string; text?: string };
type Section = { title: string; detail: string; citations: Citation[] };
type EscalateStatus = "pending" | "approved" | "denied" | null;
type Msg = {
  role: "user" | "ai";
  content: string;
  step?: string;
  citations?: Citation[];
  steps_log?: string[];
  refusal?: boolean;
  escalate_id?: string;
  escalate_status?: EscalateStatus;
  suggested_query?: string;
  suggest_reason?: string;
  suggest_used?: boolean;
  sections?: Section[];
};
type Conversation = { id: string; title: string; messages: Msg[] };

const SUGGESTIONS = [
  "Thời gian thử việc tối đa là bao lâu?",
  "Thời giờ làm việc bình thường trong một ngày tối đa bao nhiêu?",
  "Tuổi nghỉ hưu của người lao động hiện nay là bao nhiêu?",
  "Trường hợp nào được đơn phương chấm dứt hợp đồng lao động?",
];

const STORE_KEY = "llv_conversations";

function loadConvos(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}
function saveConvos(c: Conversation[]) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(c.slice(0, 30)));
  } catch {
    /* ignore */
  }
}

/** Ước lượng token tiếng Việt: ~1.3 token/từ */
function estimateTokens(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.ceil(words * 1.3);
}

// --- icons ---
const IconMenu = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M3 6h18M3 12h18M3 18h18" />
  </svg>
);
const IconPlus = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
);
const IconSend = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />
  </svg>
);
const IconLock = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);
const IconChevron = ({ open }: { open: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.15s" }}>
    <path d="M9 18l6-6-6-6" />
  </svg>
);
const IconCheck = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
    <path d="M5 13l4 4L19 7" />
  </svg>
);
const IconSun = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
  </svg>
);
const IconMoon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
);
const IconGraph = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="5" cy="12" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/>
    <line x1="7" y1="11.5" x2="17" y2="6.5"/><line x1="7" y1="12.5" x2="17" y2="17.5"/>
  </svg>
);
const IconDash = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
  </svg>
);
const IconSearch = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
  </svg>
);

// ---------- ApprovalCard ----------
function ApprovalCard({
  question,
  threadId,
  status,
  onApprove,
  onDeny,
}: {
  question: string;
  threadId: string | null;
  status: EscalateStatus;
  onApprove: () => void;
  onDeny: () => void;
}) {
  if (status === "approved") {
    return (
      <div className="approval-card approved">
        <div className="approval-header">
          <span className="approval-icon"><IconCheck /></span>
          <span className="approval-title">ĐÃ GỬI CHO NHÀ PHÁT HÀNH</span>
          <span className="approval-badge">escalate_refusal</span>
        </div>
        <p className="approval-note">Câu hỏi đã được ghi nhận. Nhà phát hành sẽ bổ sung dữ liệu hoặc trả lời trực tiếp.</p>
      </div>
    );
  }
  if (status === "denied") {
    return (
      <div className="approval-card denied">
        <div className="approval-header">
          <span className="approval-title">ĐÃ TỪ CHỐI</span>
        </div>
        <p className="approval-note">Câu hỏi không được gửi đi.</p>
      </div>
    );
  }

  return (
    <div className="approval-card">
      <div className="approval-header">
        <span className="approval-icon"><IconLock /></span>
        <span className="approval-title">CẦN PHÊ DUYỆT</span>
        <span className="approval-badge">escalate_refusal</span>
      </div>
      <p className="approval-desc">Trợ lý muốn gửi câu hỏi này cho <strong>nhà phát hành</strong> để xem xét bổ sung dữ liệu.</p>
      <div className="approval-fields">
        <div className="af-row">
          <div className="af-col">
            <div className="af-label">CÂU HỎI</div>
            <div className="af-val">{question}</div>
          </div>
          <div className="af-col">
            <div className="af-label">HÀNH ĐỘNG</div>
            <div className="af-val">Ghi nhận &amp; thông báo</div>
          </div>
        </div>
        <div className="af-row">
          <div className="af-col">
            <div className="af-label">THREAD</div>
            <div className="af-val">{threadId || "—"}</div>
          </div>
          <div className="af-col">
            <div className="af-label">TRẠNG THÁI</div>
            <div className="af-val">Chờ phê duyệt</div>
          </div>
        </div>
      </div>
      <div className="approval-actions">
        <button className="btn-approve" onClick={onApprove}><IconCheck /> PHÊ DUYỆT</button>
        <button className="btn-deny" onClick={onDeny}>✕ TỪ CHỐI</button>
        <span className="approval-footer-note">câu hỏi chưa được gửi cho đến khi bạn phê duyệt</span>
      </div>
    </div>
  );
}

// ---------- StepTimeline ----------
function StepTimeline({ steps }: { steps: string[] }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;
  return (
    <div className="step-timeline">
      <button className="step-toggle" onClick={() => setOpen((v) => !v)}>
        <IconChevron open={open} />
        <IconSearch />
        <span>Luồng tra cứu ({steps.length} bước)</span>
      </button>
      {open && (
        <div className="step-list">
          {steps.map((s, i) => (
            <div key={i} className="step-row">
              <span className="step-dot-done"><IconCheck /></span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- SectionAccordion — từng ý thành toggle ----------
function SectionAccordion({ sections }: { sections: Section[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!sections || sections.length === 0) return null;
  return (
    <div className="section-accordion">
      {sections.map((s, i) => {
        const isOpen = open === i;
        return (
          <div key={i} className={`section-item ${isOpen ? "open" : ""}`}>
            <button
              className="section-toggle"
              onClick={() => setOpen(isOpen ? null : i)}
              aria-expanded={isOpen}
            >
              <IconChevron open={isOpen} />
              <span className="section-num">{i + 1}.</span>
              <span className="section-title">{s.title}</span>
            </button>
            {isOpen && (
              <div className="section-body">
                <div className="section-detail">{s.detail}</div>
                {s.citations && s.citations.length > 0 && (
                  <div className="section-sources">
                    {s.citations.map((c, j) => (
                      <span
                        key={j}
                        className="chip"
                        title={c.text || c.node_id}
                        onClick={() => {
                          const el = document.getElementById(`cite-panel-${c.node_id}`);
                          if (el) el.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        {c.display || c.node_id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------- SuggestRewrite — đề xuất câu hỏi pháp lý chuẩn hơn ----------
const IconRefresh = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
  </svg>
);

function SuggestRewrite({
  suggested,
  reason,
  used,
  onUse,
  onIgnore,
}: {
  suggested: string;
  reason: string;
  used?: boolean;
  onUse: () => void;
  onIgnore: () => void;
}) {
  if (used) {
    return (
      <div className="rewrite-card used">
        <span className="rewrite-icon"><IconRefresh /></span>
        <span className="rewrite-used-label">Đã tìm lại với câu hỏi chuẩn pháp lý.</span>
      </div>
    );
  }
  return (
    <div className="rewrite-card">
      <div className="rewrite-header">
        <span className="rewrite-icon"><IconRefresh /></span>
        <span className="rewrite-title">Đề xuất câu hỏi pháp lý chuẩn hơn</span>
      </div>
      {reason && <p className="rewrite-reason">{reason}</p>}
      <div className="rewrite-suggested">"{suggested}"</div>
      <div className="rewrite-actions">
        <button className="btn-use-rewrite" onClick={onUse}>
          <IconCheck /> Dùng câu này
        </button>
        <button className="btn-deny" onClick={onIgnore}>✕ Bỏ qua</button>
      </div>
    </div>
  );
}

// ---------- CitationList — chip bấm toggle mở/đóng text ----------
function CitationList({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className="citations">
      {/* Dãy chip */}
      <div className="chip-row">
        {citations.map((c, j) => {
          const n = c.n ?? j + 1;
          const isOpen = open === n;
          return (
            <button
              key={j}
              className={`chip ${isOpen ? "active" : ""}`}
              onClick={() => setOpen(isOpen ? null : n)}
              aria-expanded={isOpen}
            >
              <span className="n">[{n}]</span> {c.display || c.node_id}
              <span className="chip-arrow">{isOpen ? "▲" : "▼"}</span>
            </button>
          );
        })}
      </div>

      {/* Panel mở rộng */}
      {open !== null && (() => {
        const c = citations.find((x, j) => (x.n ?? j + 1) === open);
        if (!c) return null;
        return (
          <div className="citation-panel">
            <div className="citation-panel-head">{c.display || c.node_id}</div>
            <div className="citation-panel-body">{c.text || "Không có nội dung."}</div>
          </div>
        );
      })()}
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  const threadId = useRef<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Đếm token thời gian thực
  const inputWords = input.trim().split(/\s+/).filter(Boolean).length;
  const inputTokens = estimateTokens(input);
  const showCounter = input.trim().length > 0;

  useEffect(() => {
    const saved_convos = loadConvos();
    setConvos(saved_convos);
    // Khôi phục theme
    try {
      const saved = localStorage.getItem("llv_theme") as "light" | "dark" | "system" | null;
      if (saved && saved !== "system") {
        setTheme(saved);
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch { /* ignore */ }
    // Khôi phục cuộc trò chuyện từ URL ?t=<id>
    try {
      const tid = new URLSearchParams(window.location.search).get("t");
      if (tid) {
        const match = saved_convos.find((c) => c.id === tid);
        if (match) {
          setMessages(match.messages);
          setActiveId(match.id);
          threadId.current = match.id;
        }
      }
    } catch { /* ignore */ }
  }, []);

  function toggleTheme() {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("llv_theme", next); } catch { /* ignore */ }
      return next;
    });
  }

  function scrollDown() {
    requestAnimationFrame(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight }));
  }

  function newChat() {
    setMessages([]);
    setActiveId(null);
    threadId.current = null;
    setUrl(null);
  }

  function openConvo(c: Conversation) {
    setMessages(c.messages);
    setActiveId(c.id);
    threadId.current = c.id;
    setUrl(c.id);
    scrollDown();
  }

  function genId(): string {
    try { return crypto.randomUUID().replace(/-/g, "").slice(0, 12); }
    catch { return Math.random().toString(16).slice(2, 14); }
  }

  function setUrl(id: string | null) {
    const url = id ? `/?t=${id}` : "/";
    setTimeout(() => window.history.replaceState(null, "", url), 0);
  }

  function persist(msgs: Msg[]) {
    const id = threadId.current || genId();
    threadId.current = id;
    setUrl(id);
    const title = msgs.find((m) => m.role === "user")?.content.slice(0, 48) || "Cuộc trò chuyện";
    setConvos((prev) => {
      const rest = prev.filter((c) => c.id !== id);
      const next = [{ id, title, messages: msgs }, ...rest];
      saveConvos(next);
      return next;
    });
    setActiveId(id);
  }

  async function escalate(question: string, msgIdx: number) {
    try {
      const res = await fetch(`${API_BASE}/api/escalate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, thread_id: threadId.current }),
      });
      const data = await res.json();
      setMessages((msgs) =>
        msgs.map((m, i) => (i === msgIdx ? { ...m, escalate_id: data.id, escalate_status: "approved" } : m))
      );
    } catch {
      // Nếu API lỗi, vẫn đánh dấu approved trên UI
      setMessages((msgs) =>
        msgs.map((m, i) => (i === msgIdx ? { ...m, escalate_status: "approved" } : m))
      );
    }
  }

  function denyEscalate(msgIdx: number) {
    setMessages((msgs) =>
      msgs.map((m, i) => (i === msgIdx ? { ...m, escalate_status: "denied" } : m))
    );
  }

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);

    const history = messages.map((m) => ({ role: m.role === "ai" ? "assistant" : "user", content: m.content }));
    const base: Msg[] = [
      ...messages,
      { role: "user", content: q },
      { role: "ai", content: "", steps_log: [] },
    ];
    setMessages(base);
    scrollDown();

    // Cập nhật BẤT BIẾN: luôn tạo object mới, không mutate.
    const update = (fn: (ai: Msg) => Msg) =>
      setMessages((m) => m.map((x, i) => (i === m.length - 1 && x.role === "ai" ? fn(x) : x)));

    try {
      await streamChat(API_BASE, { message: q, thread_id: threadId.current, history }, (event, data) => {
        if (event === "start") threadId.current = threadId.current || data.thread_id;
        else if (event === "step")
          update((ai) => ({
            ...ai,
            step: data.label,
            steps_log: [...(ai.steps_log ?? []), data.label],
          }));
        else if (event === "token") update((ai) => ({ ...ai, content: ai.content + (data.text ?? "") }));
        else if (event === "citation")
          update((ai) => ({ ...ai, citations: [...(ai.citations ?? []), data] }));
        else if (event === "section")
          update((ai) => ({ ...ai, sections: [...(ai.sections ?? []), data as Section] }));
        else if (event === "suggest_rewrite")
          update((ai) => ({ ...ai, suggested_query: data.suggested, suggest_reason: data.reason }));
        else if (event === "error") update((ai) => ({ ...ai, content: ai.content + `\n\n⚠️ ${data.message}` }));
        else if (event === "done") {
          update((ai) => {
            const isRefusal = ai.content.trim().startsWith(REFUSAL.slice(0, 20));
            return {
              ...ai,
              step: undefined,
              refusal: isRefusal,
              escalate_status: isRefusal ? "pending" : null,
            };
          });
        }
        scrollDown();
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Lỗi không xác định";
      update((ai) => ({ ...ai, content: ai.content + `\n\n⚠️ Lỗi kết nối: ${msg}` }));
    } finally {
      setBusy(false);
      setMessages((m) => {
        const copy = m.map((x) => ({ ...x, step: undefined }));
        persist(copy);
        return copy;
      });
    }
  }

  return (
    <div className="shell">
      <aside className={`sidebar ${sidebarOpen ? "" : "closed"}`}>
        <div className="brand">
          <div className="logo">L</div>
          <div>
            <div className="name">Trợ lý Luật Lao động</div>
            <div className="sub">Hỏi đáp có trích dẫn</div>
          </div>
        </div>

        <button className="new-chat" onClick={newChat}>
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
            <div
              key={c.id}
              className={`thread-item ${c.id === activeId ? "active" : ""}`}
              title={c.title}
            >
              <span className="thread-title" onClick={() => openConvo(c)}>{c.title}</span>
              <button
                className="thread-del"
                title="Xóa cuộc trò chuyện"
                onClick={(e) => {
                  e.stopPropagation();
                  setConvos((prev) => {
                    const next = prev.filter((x) => x.id !== c.id);
                    saveConvos(next);
                    return next;
                  });
                  if (activeId === c.id) { setMessages([]); setActiveId(null); threadId.current = null; setUrl(null); }
                }}
              >···</button>
            </div>
          ))}
        </div>

        <div className="side-foot">
          Nguồn: BLLĐ 2019 · 2012 · NĐ 145/2020 · án lệ lao động. Câu trả lời kèm trích dẫn Điều–Khoản.
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <button className="icon-btn" onClick={() => setSidebarOpen((v) => !v)} aria-label="Ẩn/hiện thanh bên">
            <IconMenu />
          </button>
          <span className="title">Trợ lý pháp luật lao động</span>
          <Link href="/graph" className="graph-nav-btn" title="Knowledge Graph">
            <IconGraph />
          </Link>
          <button className="theme-btn" onClick={toggleTheme} aria-label="Đổi chế độ sáng/tối">
            {theme === "dark" ? <><IconSun /> Sáng</> : <><IconMoon /> Tối</>}
          </button>
        </header>

        <div className="messages" ref={listRef}>
          {messages.length === 0 ? (
            <div className="messages-inner">
              <div className="empty">
                <div className="logo" style={{ width: 44, height: 44, fontSize: 20, borderRadius: 12 }}>L</div>
                <h2>Hỏi đáp pháp luật lao động</h2>
                <p>Trả lời kèm trích dẫn Điều – Khoản – Điểm, biết hiệu lực theo thời gian.</p>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} className="suggestion" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
                <Link href="/graph" className="empty-graph-btn">
                  <IconGraph /> Xem Knowledge Graph embedding
                </Link>
              </div>
            </div>
          ) : (
            <div className="messages-inner">
              {messages.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  <div className="bubble">
                    {/* Bước đang chạy (realtime) */}
                    {m.step && (
                      <div className="step">
                        <span className="dot" /> {m.step}…
                      </div>
                    )}

                    {/* Nội dung tin nhắn */}
                    {m.role === "ai" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || (m.step ? "" : "…")}</ReactMarkdown>
                    ) : (
                      m.content
                    )}

                    {/* Accordion sections */}
                    {m.role === "ai" && (m.sections?.length ?? 0) > 0 && (
                      <SectionAccordion sections={m.sections!} />
                    )}

                    {/* Suggest rewrite card */}
                    {m.suggested_query && m.role === "ai" && (
                      <SuggestRewrite
                        suggested={m.suggested_query}
                        reason={m.suggest_reason || ""}
                        used={m.suggest_used}
                        onUse={() => {
                          setMessages((msgs) =>
                            msgs.map((x, idx) => idx === i ? { ...x, suggest_used: true } : x)
                          );
                          send(m.suggested_query!);
                        }}
                        onIgnore={() =>
                          setMessages((msgs) =>
                            msgs.map((x, idx) => idx === i ? { ...x, suggested_query: undefined } : x)
                          )
                        }
                      />
                    )}

                    {/* Approval card — chỉ hiện khi bị từ chối */}
                    {m.refusal && m.role === "ai" && (
                      <ApprovalCard
                        question={
                          messages[i - 1]?.role === "user" ? messages[i - 1].content : ""
                        }
                        threadId={threadId.current}
                        status={m.escalate_status ?? "pending"}
                        onApprove={() =>
                          escalate(
                            messages[i - 1]?.role === "user" ? messages[i - 1].content : "",
                            i
                          )
                        }
                        onDeny={() => denyEscalate(i)}
                      />
                    )}

                    {/* Luồng tra cứu (collapsible) */}
                    {m.role === "ai" && !m.step && (m.steps_log?.length ?? 0) > 0 && (
                      <StepTimeline steps={m.steps_log!} />
                    )}

                    {/* Trích dẫn — bấm chip để mở/đóng nội dung */}
                    {m.citations && m.citations.length > 0 && (
                      <CitationList citations={m.citations} />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="composer-wrap">
          <div className="composer">
            <div className="box">
              <textarea
                value={input}
                placeholder="Nhập câu hỏi về luật lao động…"
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={1}
              />
              {showCounter && (
                <div className="token-counter">
                  {inputWords} từ · ~{inputTokens} token
                </div>
              )}
            </div>
            <button className="send" onClick={() => send()} disabled={busy} aria-label="Gửi">
              <IconSend />
            </button>
          </div>
          <div className="hint">Thông tin mang tính tham khảo, luôn đối chiếu văn bản gốc được trích dẫn.</div>
        </div>
      </main>
    </div>
  );
}
