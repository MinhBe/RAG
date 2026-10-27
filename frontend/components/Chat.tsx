"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { streamChat, type Done, type Source, type Step, type Turn } from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: Step[];
  sources?: Source[];
  done?: Done;
  error?: string;
};

const SAMPLES = [
  "Áo mua online được đổi trong bao nhiêu ngày?",
  "Thanh toán bằng Visa thì bao lâu được hoàn tiền?",
  "Sofa được bảo hành mấy năm?",
  "hoan tien ve vi momo mat bao lau",
];

// Turn "[2]" into a markdown link so the renderer can show a clickable citation chip.
function linkCitations(text: string, msgId: string) {
  return text.replace(/\[(\d+)\]/g, (_, n) => `[${n}](#src-${msgId}-${n})`);
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, which React
    // would otherwise treat as the effect's cleanup function.
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function patch(id: string, fn: (m: Message) => Message) {
    setMessages((all) => all.map((m) => (m.id === id ? fn(m) : m)));
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const history: Turn[] = messages
      .filter((m) => !m.error && m.content)
      .map((m) => ({ role: m.role, content: m.content }));
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: question };
    const botId = crypto.randomUUID();
    setMessages((all) => [...all, userMsg, { id: botId, role: "assistant", content: "", steps: [] }]);
    setInput("");
    setBusy(true);
    abortRef.current = new AbortController();

    try {
      await streamChat(
        question,
        history,
        {
          onStep: (step) => patch(botId, (m) => ({ ...m, steps: [...(m.steps ?? []), step] })),
          onSources: (sources) => patch(botId, (m) => ({ ...m, sources })),
          onToken: (t) => patch(botId, (m) => ({ ...m, content: m.content + t })),
          onDone: (done) => patch(botId, (m) => ({ ...m, done })),
          onError: (error) => patch(botId, (m) => ({ ...m, error })),
        },
        abortRef.current.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        patch(botId, (m) => ({ ...m, error: "Không kết nối được tới máy chủ." }));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            <p>Hỏi về chính sách đổi trả, hoàn tiền, bảo hành, vận chuyển hoặc thanh toán của Mộc An Home.</p>
            <div className="samples">
              {SAMPLES.map((s) => (
                <button key={s} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="bubble user">
              {m.content}
            </div>
          ) : (
            <div key={m.id} className="bubble bot">
              {!!m.steps?.length && (
                <ol className="steps">
                  {m.steps.map((s, i) => (
                    <li key={i} className={i === m.steps!.length - 1 && !m.done ? "running" : ""}>
                      {s.label}
                      {s.ms !== undefined && <span className="muted"> · {s.ms} ms</span>}
                    </li>
                  ))}
                </ol>
              )}

              <div className="answer">
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => {
                      const n = href?.split("-").pop();
                      return (
                        <a
                          className="cite"
                          href={href}
                          onMouseEnter={() => setActive(`${m.id}-${n}`)}
                          onMouseLeave={() => setActive(null)}
                          onClick={() => {
                            // Open the collapsed source list so the anchor jump lands on the card.
                            document.getElementById(href?.slice(1) ?? "")?.closest("details")?.setAttribute("open", "");
                          }}
                        >
                          {children}
                        </a>
                      );
                    },
                  }}
                >
                  {linkCitations(m.content, m.id)}
                </ReactMarkdown>
                {busy && !m.done && !m.error && <span className="caret" />}
              </div>

              {m.error && <div className="error">{m.error}</div>}

              {!!m.sources?.length && (
                <details className="sources">
                  <summary>Nguồn ({m.sources.length})</summary>
                  {m.sources.map((s) => {
                    const cited = m.done?.citations.includes(s.n);
                    return (
                      <div
                        key={s.n}
                        id={`src-${m.id}-${s.n}`}
                        className={`source ${cited ? "cited" : ""} ${active === `${m.id}-${s.n}` ? "active" : ""}`}
                      >
                        <div className="source-head">
                          <span className="badge">{s.n}</span>
                          <strong>{s.doc_title}</strong>
                          <span className="muted"> › {s.section}</span>
                        </div>
                        <pre>{s.text}</pre>
                        <div className="muted small">
                          {s.chunk_id} · BM25 #{s.bm25_rank ?? "–"} · vector #{s.dense_rank ?? "–"}
                        </div>
                      </div>
                    );
                  })}
                </details>
              )}

              {m.done && (
                <div className="metrics muted small">
                  {m.done.llm} · truy xuất {m.done.latency_ms.retrieval} ms · token đầu{" "}
                  {m.done.latency_ms.first_token ?? "–"} ms · tổng {m.done.latency_ms.total} ms
                  {m.done.usage && m.done.usage.input_tokens > 0 && (
                    <>
                      {" "}
                      · {m.done.usage.input_tokens}→{m.done.usage.output_tokens} token · $
                      {m.done.usage.cost_usd.toFixed(5)}
                    </>
                  )}
                  {m.done.invalid_citations.length > 0 && (
                    <span className="warn"> · trích dẫn không hợp lệ: {m.done.invalid_citations.join(", ")}</span>
                  )}
                </div>
              )}
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Nhập câu hỏi, ví dụ: đổi size áo mất phí không?"
          maxLength={2000}
          aria-label="Câu hỏi"
        />
        {busy ? (
          <button type="button" onClick={() => abortRef.current?.abort()}>
            Dừng
          </button>
        ) : (
          <button type="submit" disabled={!input.trim()}>
            Gửi
          </button>
        )}
      </form>
    </div>
  );
}
