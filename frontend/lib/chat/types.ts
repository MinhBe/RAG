export type Citation = { n?: number; node_id: string; display?: string; text?: string };
export type Section = { title: string; detail: string; citations: Citation[] };
/* Vòng phê duyệt có người thật:
   pending  -> người dùng chưa quyết gửi hay không
   denied   -> người dùng chọn không gửi
   waiting  -> đã gửi, chờ chuyên gia trên /dashboard ("approved" là giá trị cũ cùng nghĩa)
   answered -> chuyên gia đã duyệt và trả lời (escalate_reply)
   rejected -> chuyên gia từ chối (escalate_reply là lý do) */
export type EscalateStatus = "pending" | "denied" | "waiting" | "approved" | "answered" | "rejected" | null;

export type Msg = {
  role: "user" | "ai";
  content: string;
  step?: string;
  citations?: Citation[];
  steps_log?: string[];
  refusal?: boolean;
  escalate_id?: string;
  escalate_status?: EscalateStatus;
  escalate_reply?: string;
  suggested_query?: string;
  suggest_reason?: string;
  suggest_used?: boolean;
  sections?: Section[];
};

export type Conversation = { id: string; title: string; messages: Msg[] };
