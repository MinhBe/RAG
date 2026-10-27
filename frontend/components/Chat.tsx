"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat } from "@/lib/sse";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type Citation = { n?: number; node_id: string; display?: string; text?: string };
type Msg = {
  role: "user" | "ai";
  content: string;
  step?: string;
  citations?: Citation[];
};

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const threadId = useRef<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  function scrollDown() {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    });
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);

    const history = messages.map((m) => ({
      role: m.role === "ai" ? "assistant" : "user",
      content: m.content,
    }));

    setMessages((m) => [...m, { role: "user", content: text }, { role: "ai", content: "" }]);
    scrollDown();

    const update = (fn: (ai: Msg) => void) =>
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last && last.role === "ai") fn(last);
        return copy;
      });

    try {
      await streamChat(
        API_BASE,
        { message: text, thread_id: threadId.current, history },
        (event, data) => {
          if (event === "start") threadId.current = data.thread_id;
          else if (event === "step") update((ai) => (ai.step = data.label));
          else if (event === "token") update((ai) => (ai.content += data.text ?? ""));
          else if (event === "citation")
            update((ai) => (ai.citations = [...(ai.citations ?? []), data]));
          else if (event === "error")
            update((ai) => (ai.content += `\n\n⚠️ ${data.message}`));
          else if (event === "done") update((ai) => (ai.step = undefined));
          scrollDown();
        },
      );
    } catch (e: any) {
      update((ai) => (ai.content += `\n\n⚠️ Lỗi kết nối: ${e.message}`));
    } finally {
      setBusy(false);
      update((ai) => (ai.step = undefined));
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h1>Trợ lý pháp luật lao động</h1>
        <p>Hỏi đáp luật lao động Việt Nam, có trích dẫn điều – khoản – điểm.</p>
      </div>

      <div className="messages" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty">
            Hãy đặt một câu hỏi về luật lao động. Ví dụ: “Thời gian thử việc tối đa là bao lâu?”
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">
              {m.step && <div className="step">● {m.step}…</div>}
              {m.role === "ai" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {m.content || (m.step ? "" : "…")}
                </ReactMarkdown>
              ) : (
                m.content
              )}
              {m.citations && m.citations.length > 0 && (
                <div className="citations">
                  {m.citations.map((c, j) => (
                    <span
                      className="chip"
                      key={j}
                      title={c.text || c.node_id}
                      onClick={() => alert(`${c.display || c.node_id}\n\n${c.text || ""}`)}
                    >
                      [{c.n ?? j + 1}] {c.display || c.node_id}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="composer">
        <textarea
          value={input}
          placeholder="Nhập câu hỏi…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button onClick={send} disabled={busy}>
          {busy ? "…" : "Gửi"}
        </button>
      </div>
    </div>
  );
}
