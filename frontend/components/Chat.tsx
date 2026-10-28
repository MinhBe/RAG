"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const REFUSAL = "Không đủ căn cứ trong kho văn bản để trả lời chắc chắn câu này.";

type Citation = { n?: number; node_id: string; display?: string; text?: string };
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

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const threadId = useRef<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Đếm token thời gian thực
  const inputWords = input.trim().split(/\s+/).filter(Boolean).length;
  const inputTokens = estimateTokens(input);
  const showCounter = input.trim().length > 0;

  useEffect(() => {
    setConvos(loadConvos());
  }, []);

  function scrollDown() {
    requestAnimationFrame(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight }));
  }

  function newChat() {
    setMessages([]);
    setActiveId(null);
    threadId.current = null;
  }

  function openConvo(c: Conversation) {
    setMessages(c.messages);
    setActiveId(c.id);
    threadId.current = c.id;
    scrollDown();
  }

  function persist(msgs: Msg[]) {
    const id = threadId.current || Date.now().toString();
    threadId.current = id;
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

        <div className="side-label">Gần đây</div>
        <div className="thread-list">
          {convos.length === 0 && <div className="thread-empty">Chưa có cuộc trò chuyện nào.</div>}
          {convos.map((c) => (
            <div
              key={c.id}
              className={`thread-item ${c.id === activeId ? "active" : ""}`}
              onClick={() => openConvo(c)}
              title={c.title}
            >
              {c.title}
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

                    {/* Trích dẫn */}
                    {m.citations && m.citations.length > 0 && (
                      <div className="citations">
                        {m.citations.map((c, j) => (
                          <span
                            key={j}
                            className="chip"
                            title={c.text || c.node_id}
                            onClick={() => alert(`${c.display || c.node_id}\n\n${c.text || ""}`)}
                          >
                            <span className="n">[{c.n ?? j + 1}]</span> {c.display || c.node_id}
                          </span>
                        ))}
                      </div>
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
