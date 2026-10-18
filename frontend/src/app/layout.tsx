import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Runwise | AI Agent Reliability Infrastructure & Playground",
  description:
    "Production-grade customer support AI agent platform with deterministic grading, OpenTelemetry LLMOps, and cost-aware auto-routing.",
  keywords: [
    "AI Agent",
    "LLMOps",
    "Auto-Routing",
    "OpenTelemetry",
    "Deterministic Evaluation",
    "Gemini 2.5",
    "FastAPI",
  ],
  authors: [{ name: "Amey Narwadkar", url: "https://github.com/ameynarwadkar" }],
  openGraph: {
    title: "Runwise | AI Agent Reliability Infrastructure",
    description:
      "Evaluate reliability. Observe every execution. Route intelligently to reduce cost without sacrificing correctness.",
    url: "https://runwise.dev",
    siteName: "Runwise",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        suppressHydrationWarning
        className={`${inter.variable} ${jetbrainsMono.variable} antialiased min-h-screen bg-charcoal text-slate-100 selection:bg-brand-orange selection:text-white`}
      >
        {children}
      </body>
    </html>
  );
}
