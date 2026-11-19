import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Sidebar } from "@/components/Sidebar";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "My API Integration Assistant",
  description: "Personal AI assistant for API integration projects",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-slate-50 md:flex-row">
        <Sidebar />
        <main className="flex-1 p-4 md:h-screen md:overflow-y-auto md:p-8">{children}</main>
      </body>
    </html>
  );
}
