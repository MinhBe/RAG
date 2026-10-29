export type Citation = { n?: number; node_id: string; display?: string; text?: string };
export type Section = { title: string; detail: string; citations: Citation[] };
export type EscalateStatus = "pending" | "approved" | "denied" | null;

export type Msg = {
  role: "user" | "ai";
  content: string;
  step?: string;
  citations?: Citation[];
  steps_log?: string[];
  refusal?: boolean;
  escalate_id?: string;
  escalate_status?: EscalateStatus;
  suggested_query?: string;
  suggest_reason?: string;
  suggest_used?: boolean;
  sections?: Section[];
};

export type Conversation = { id: string; title: string; messages: Msg[] };
