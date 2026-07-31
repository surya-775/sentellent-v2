import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentellent Stock Analyst",
  description: "Agentic AI Indian Equity Research Chief of Staff",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
