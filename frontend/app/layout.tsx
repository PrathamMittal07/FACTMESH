import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FactMesh — Fact Knowledge Layer",
  description:
    "Extract, ground, and reconcile facts across PDF documents. Built for the Superjoin VIT 2026 Engineering Intern Assignment.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="navbar">
          <div className="navbar-inner">
            <Link href="/" className="navbar-brand">
              ◆ <span>FactMesh</span>
            </Link>
            <div className="navbar-links">
              <Link href="/">Documents</Link>
              <Link href="/relationships">Relationships</Link>
              <Link href="/issues">Issues</Link>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
