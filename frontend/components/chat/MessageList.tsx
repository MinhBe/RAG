"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  ApprovalCard, CitationList, SectionAccordion, StepTimeline, SuggestRewrite,
} from "@/components/chat/AnswerParts";
import { IconGraph } from "@/components/chat/icons";
import type { Msg } from "@/lib/chat/types";

const SUGGESTIONS = [
  "Thời gian thử việc tối đa là bao lâu?",
  "Thời giờ làm việc bình thường trong một ngày tối đa bao nhiêu?",
  "Tuổi nghỉ hưu của người lao động hiện nay là bao nhiêu?",
  "Trường hợp nào được đơn phương chấm dứt hợp đồng lao động?",
];

export default function MessageList({
  messages, threadId, listRef, onAsk, onUseSuggestion, onIgnoreSuggestion, onEscalate, onDeny,
}: {
  messages: Msg[];
  threadId: string | null;
  listRef: React.RefObject<HTMLDivElement | null>;
  onAsk: (q: string) => void;
  onUseSuggestion: (msgIdx: number, q: string) => void;
  onIgnoreSuggestion: (msgIdx: number) => void;
  onEscalate: (question: string, msgIdx: number) => void;
  onDeny: (msgIdx: number) => void;
}) {
  // the user turn just above an AI message is the question it answered
  const questionBefore = (i: number) => (messages[i - 1]?.role === "user" ? messages[i - 1].content : "");

  return (
    <div className="messages" ref={listRef}>
      {messages.length === 0 ? (
        <div className="messages-inner">
          <div className="empty">
            <div className="logo" style={{ width: 44, height: 44, fontSize: 20, borderRadius: 12 }}>L</div>
            <h2>Hỏi đáp pháp luật lao động</h2>
            <p>Trả lời kèm trích dẫn Điều – Khoản – Điểm, biết hiệu lực theo thời gian.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion" onClick={() => onAsk(s)}>
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
                {/* bước đang chạy (realtime) */}
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

                {m.role === "ai" && (m.sections?.length ?? 0) > 0 && (
                  <SectionAccordion sections={m.sections!} />
                )}

                {m.suggested_query && m.role === "ai" && (
                  <SuggestRewrite
                    suggested={m.suggested_query}
                    reason={m.suggest_reason || ""}
                    used={m.suggest_used}
                    onUse={() => onUseSuggestion(i, m.suggested_query!)}
                    onIgnore={() => onIgnoreSuggestion(i)}
                  />
                )}

                {/* thẻ phê duyệt chỉ hiện khi bị từ chối */}
                {m.refusal && m.role === "ai" && (
                  <ApprovalCard
                    question={questionBefore(i)}
                    threadId={threadId}
                    status={m.escalate_status ?? "pending"}
                    onApprove={() => onEscalate(questionBefore(i), i)}
                    onDeny={() => onDeny(i)}
                  />
                )}

                {m.role === "ai" && !m.step && (m.steps_log?.length ?? 0) > 0 && (
                  <StepTimeline steps={m.steps_log!} />
                )}

                {m.citations && m.citations.length > 0 && (
                  <CitationList citations={m.citations} />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
