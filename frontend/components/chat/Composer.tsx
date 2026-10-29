import { IconSend } from "@/components/chat/icons";
import { estimateTokens } from "@/lib/chat/storage";

export default function Composer({ value, onChange, onSubmit, busy }: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  const words = value.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="composer-wrap">
      <div className="composer">
        <div className="box">
          <textarea
            value={value}
            placeholder="Nhập câu hỏi về luật lao động…"
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
            rows={1}
          />
          {value.trim().length > 0 && (
            <div className="token-counter">
              {words} từ · ~{estimateTokens(value)} token
            </div>
          )}
        </div>
        <button className="send" onClick={onSubmit} disabled={busy} aria-label="Gửi">
          <IconSend />
        </button>
      </div>
      <div className="hint">Thông tin mang tính tham khảo, luôn đối chiếu văn bản gốc được trích dẫn.</div>
    </div>
  );
}
