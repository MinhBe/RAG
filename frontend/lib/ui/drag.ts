/* Kéo bằng con trỏ: dùng chung cho kéo nền bản đồ và hai tay kéo đổi kích thước. */
export function startDrag(
  e: React.PointerEvent,
  onMove: (dx: number, dy: number) => void,
  onEnd?: () => void,
) {
  e.preventDefault();
  const sx = e.clientX, sy = e.clientY;
  const move = (m: PointerEvent) => onMove(m.clientX - sx, m.clientY - sy);
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    document.body.style.userSelect = "";
    onEnd?.();
  };
  document.body.style.userSelect = "none";
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

/* localStorage có thể bị chặn (chế độ riêng tư): lỗi thì bỏ qua, giữ mặc định */
export function saveNumber(key: string, v: number) {
  try { localStorage.setItem(key, String(Math.round(v))); } catch { /* ignore */ }
}

export function loadNumber(key: string): number {
  try { return Number(localStorage.getItem(key)) || 0; } catch { return 0; }
}
