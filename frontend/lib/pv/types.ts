/* Dữ liệu trả về từ GET /api/pv (backend/app/pv/library.py). */

export type PvItem = {
  id: string;
  title: string;
  group: string;
  layer: string;
  source: string;
  tags: string[];
  files: string[];
  question: string;
  technical: string;
  consulting: string;
  negotiation: string;
};

export type PvGroup = { group: string; title: string; part: string; items: PvItem[] };

export type PvLibrary = { layers: Record<string, string>; groups: PvGroup[] };

export const PARTS: { key: keyof PvItem; label: string }[] = [
  { key: "technical", label: "Chốt kỹ thuật" },
  { key: "consulting", label: "Ví dụ tư vấn" },
  { key: "negotiation", label: "Ví dụ đàm phán" },
];
