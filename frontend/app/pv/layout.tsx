import type { Metadata } from "next";

// trang luyện phỏng vấn: không có link trỏ tới, không cho máy tìm kiếm lập chỉ mục
export const metadata: Metadata = {
  title: "Luyện phỏng vấn",
  robots: { index: false, follow: false },
};

export default function PvLayout({ children }: { children: React.ReactNode }) {
  return children;
}
