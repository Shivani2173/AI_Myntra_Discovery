import type { ReactNode } from "react";
import { IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const display = Source_Serif_4({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-display",
});

export const metadata = {
  title: "Why they didn’t buy from wishlist",
  description: "Corpus insights on wishlist-to-purchase barriers",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body>
        <div className="shell">
          <nav>
            <strong className="brand">AI Discovery Engine</strong>
            <Link href="/">Why they didn’t buy</Link>
            <Link href="/explorer">Evidence explorer</Link>
          </nav>
          <main>{children}</main>
        </div>
        <footer className="site">
          Share of analyzed wishlist conversations.
        </footer>
      </body>
    </html>
  );
}
