import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trợ lý pháp luật lao động",
  description: "Hỏi đáp luật lao động Việt Nam có trích dẫn",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
