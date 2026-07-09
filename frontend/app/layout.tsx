import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ConstrainAI",
  description:
    "Conversational constraint solving with minimal conflict isolation and repair.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
