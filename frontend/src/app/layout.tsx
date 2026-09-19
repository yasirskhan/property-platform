// ============================================================
// Root Layout
// ------------------------------------------------------------
// This wraps every page in the app. It sets the HTML shell,
// fonts, and global styles. It stays consistent across pages.
// ============================================================

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Property Platform",
  description: "Manage properties, tenants, leases, payments, and maintenance.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}