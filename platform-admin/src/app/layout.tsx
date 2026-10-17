import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Platform Admin",
  description: "Internal Property Platform operations console",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
