import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Career Counsel",
  description: "Minimal counseling UX for education and employment decisions",
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
