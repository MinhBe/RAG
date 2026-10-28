"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Citation = { n?: number; node_id: string; display?: string; text?: string };
type Msg = { role: "user" | "ai"; content: string; step?: string; citations?: Citation[] };
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

// --- icons (inline, không cần thư viện) ---
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

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const threadId = useRef<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

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

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);

    const history = messages.map((m) => ({ role: m.role === "ai" ? "assistant" : "user", content: m.content }));
    const base = [...messages, { role: "user", content: q } as Msg, { role: "ai", content: "" } as Msg];
    setMessages(base);
    scrollDown();

    // Cập nhật BẤT BIẾN (tạo object mới) — nếu mutate, StrictMode gọi updater 2 lần
    // sẽ nhân đôi nội dung và trích dẫn.
    const update = (fn: (ai: Msg) => Msg) =>
      setMessages((m) => m.map((x, i) => (i === m.length - 1 && x.role === "ai" ? fn(x) : x)));

    try {
      await streamChat(API_BASE, { message: q, thread_id: threadId.current, history }, (event, data) => {
        if (event === "start") threadId.current = threadId.current || data.thread_id;
        else if (event === "step") update((ai) => ({ ...ai, step: data.label }));
        else if (event === "token") update((ai) => ({ ...ai, content: ai.content + (data.text ?? "") }));
        else if (event === "citation")
          update((ai) => ({ ...ai, citations: [...(ai.citations ?? []), data] }));
        else if (event === "error") update((ai) => ({ ...ai, content: ai.content + `\n\n⚠️ ${data.message}` }));
        else if (event === "done") update((ai) => ({ ...ai, step: undefined }));
        scrollDown();
      });
    } catch (e: any) {
      update((ai) => (ai.content += `\n\n⚠️ Lỗi kết nối: ${e.message}`));
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
                    {m.step && (
                      <div className="step">
                        <span className="dot" /> {m.step}…
                      </div>
                    )}
                    {m.role === "ai" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || (m.step ? "" : "…")}</ReactMarkdown>
                    ) : (
                      m.content
                    )}
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
