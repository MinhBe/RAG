import { createSSEParser } from "./sse";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Step = { agent: string; status: string; label: string; ms?: number };

export type Source = {
  n: number;
  chunk_id: string;
  doc_id: string;
  doc_title: string;
  section: string;
  text: string;
  score: number;
  bm25_rank: number | null;
  dense_rank: number | null;
};

export type Done = {
  answer: string;
  citations: number[];
  invalid_citations: number[];
  llm: string;
  usage: { model: string; input_tokens: number; output_tokens: number; cost_usd: number } | null;
  latency_ms: { retrieval: number; first_token: number | null; total: number };
};

export type Turn = { role: "user" | "assistant"; content: string };

export type ChatHandlers = {
  onStep: (step: Step) => void;
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
  onDone: (done: Done) => void;
  onError: (message: string) => void;
};

export async function streamChat(message: string, history: Turn[], h: ChatHandlers, signal?: AbortSignal) {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ message, history }),
    signal,
  });
  if (!res.ok || !res.body) {
    h.onError(`Máy chủ trả lỗi ${res.status}`);
    return;
  }

  const parser = createSSEParser(({ event, data }) => {
    const payload = JSON.parse(data);
    switch (event) {
      case "step":
        return h.onStep(payload);
      case "sources":
        return h.onSources(payload.sources);
      case "token":
        return h.onToken(payload.text);
      case "done":
        return h.onDone(payload);
      case "error":
        return h.onError(payload.message);
    }
  });

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.feed(value);
  }
  parser.flush();
}
