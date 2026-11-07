import type { Metadata } from "next";
import Script from "next/script";
import { headers } from "next/headers";
import { connection } from "next/server";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

import { Providers } from "@/components/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Lumiant Inventory Intelligence", template: "%s · Lumiant" },
  description: "Inventory intelligence on top of your existing data warehouse.",
  robots: { index: false, follow: false },
};

// Every page is rendered per request: the CSP nonce (src/proxy.ts) only exists at request time, and Next.js can
// only put it on its own inline scripts when it renders the page for that request. Prerendered shells cannot be nonced.
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  await connection();
  // Next.js nonces this script on the server; passing the same nonce as a prop keeps the client render identical, so
  // hydration does not report a nonce mismatch.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  // Geist Sans/Mono are self-hosted variable fonts (woff2 shipped in the `geist` package via next/font/local, served
  // from /_next/static): no font CDN at build or run time, so the CSP keeps font-src 'self'.
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh antialiased">
        <Script src="/theme-init.js" strategy="beforeInteractive" nonce={nonce} />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
