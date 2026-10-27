import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mộc An · Trợ lý back-office",
  description: "Trợ lý AI trả lời chính sách có trích dẫn nguồn",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
