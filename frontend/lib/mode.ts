/* Chế độ ẩn: gõ "/pv" trong ô chat để chuyển giữa trợ lý luật và trợ lý ôn phỏng vấn.
   Giao diện giữ nguyên; chỉ đổi nguồn dữ liệu phía API (mode) và các dòng chữ dưới đây.
   Lựa chọn lưu trong localStorage nên trang /graph cũng theo cùng chế độ. */
export type Mode = "law" | "pv";

const KEY = "llv_mode";

export function loadMode(): Mode {
  try { return localStorage.getItem(KEY) === "pv" ? "pv" : "law"; } catch { return "law"; }
}

export function saveMode(m: Mode) {
  try { localStorage.setItem(KEY, m); } catch { /* storage blocked: mode lasts for this page only */ }
}

export const MODE_TEXT: Record<Mode, {
  title: string; brand: string; brandSub: string; emptyTitle: string; emptySub: string;
  source: string; graphTitle: string; placeholder: string; suggestions: string[];
}> = {
  law: {
    title: "Trợ lý pháp luật lao động",
    brand: "Trợ lý Luật Lao động",
    brandSub: "Hỏi đáp có trích dẫn",
    emptyTitle: "Hỏi đáp pháp luật lao động",
    emptySub: "Trả lời kèm trích dẫn Điều – Khoản – Điểm, biết hiệu lực theo thời gian.",
    source: "Nguồn: BLLĐ 2019 · 2012 · NĐ 145/2020 · án lệ lao động. Câu trả lời kèm trích dẫn Điều–Khoản.",
    graphTitle: "Knowledge Graph · Luật Lao động",
    placeholder: "Nhập câu hỏi về luật lao động…",
    suggestions: [
      "Thời gian thử việc tối đa là bao lâu?",
      "Thời giờ làm việc bình thường trong một ngày tối đa bao nhiêu?",
      "Tuổi nghỉ hưu của người lao động hiện nay là bao nhiêu?",
      "Trường hợp nào được đơn phương chấm dứt hợp đồng lao động?",
    ],
  },
  pv: {
    title: "Trợ lý ôn phỏng vấn AI",
    brand: "Ôn phỏng vấn AI",
    brandSub: "Hỏi đáp có trích dẫn",
    emptyTitle: "Ôn phỏng vấn kỹ thuật AI / RAG / LLM",
    emptySub: "Trả lời từ bộ 221 câu hỏi phỏng vấn, trích dẫn theo mã câu.",
    source: "Nguồn: thư viện 221 câu hỏi phỏng vấn, 13 nhóm. Câu trả lời kèm mã câu.",
    graphTitle: "Knowledge Graph · Câu hỏi phỏng vấn",
    placeholder: "Nhập câu hỏi phỏng vấn AI / RAG / LLM…",
    suggestions: [
      "Chunk theo cấu trúc hay theo độ dài cố định với văn bản pháp lý?",
      "Chọn embedding model ngoài điểm MTEB thì kiểm tra gì?",
      "Khi nào nên dùng knowledge graph thay vì chỉ vector search?",
      "Khách hàng ép giảm giá dự án RAG thì trả lời thế nào?",
    ],
  },
};
