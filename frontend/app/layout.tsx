import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Career Counsel AI",
  description:
    "내신·수능·지역 선호를 바탕으로 모집결과를 읽고 대학·전형 방향을 정리하는 입시 상담 보조 도구",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
