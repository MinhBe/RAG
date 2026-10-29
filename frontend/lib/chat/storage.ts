/* Hội thoại lưu trong localStorage, tối đa 30 cái gần nhất. */
import type { Conversation } from "@/lib/chat/types";

const STORE_KEY = "llv_conversations";
const MAX_CONVERSATIONS = 30;

export function loadConvos(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveConvos(c: Conversation[]) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(c.slice(0, MAX_CONVERSATIONS)));
  } catch {
    /* storage blocked or full: the conversation just isn't kept */
  }
}

export function genId(): string {
  try { return crypto.randomUUID().replace(/-/g, "").slice(0, 12); }
  catch { return Math.random().toString(16).slice(2, 14); }
}

/** Ước lượng token tiếng Việt: ~1.3 token/từ */
export function estimateTokens(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.ceil(words * 1.3);
}
