import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "MCP Conformance Index",
  description:
    "A public, daily record of whether MCP servers are reachable, well described, and correctly priced in context.",
  openGraph: {
    title: "MCP Conformance Index",
    description:
      "Measured reachability, documentation coverage, and context tax across the public MCP registry.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
