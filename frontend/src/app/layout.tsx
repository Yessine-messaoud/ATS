import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppShell } from "@/components/app-shell";
import { THEME_SCRIPT } from "@/components/theme";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "RecruitAI", template: "%s · RecruitAI" },
  description: "AI-assisted recruitment: explainable matching with the recruiter in charge.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f6fc" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0f1f" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The theme script sets the `dark` class before hydration, hence suppressHydrationWarning on <html> only.
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full bg-canvas text-zinc-900 dark:bg-canvas-dark dark:text-zinc-100">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
