import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/Header";
import { data, fmtDateTime } from "@/lib/data";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", weight: ["200", "300", "400", "500", "600", "700"] });

export const metadata: Metadata = {
  title: { default: "Quanata Data Dictionary", template: "%s · Quanata Data Dictionary" },
  description: "Salesforce fields for Lead, Contact, Account, Bill and Monthly Driving Stats, with where each is used in Marketing Cloud journeys and Data Cloud.",
  icons: { icon: "/brand/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem('qdd-theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}` }} />
      </head>
      <body className="min-h-full flex flex-col">
        <Header />
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-8">{children}</main>
        <footer className="rule mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex flex-col sm:flex-row gap-2 sm:items-center justify-between text-xs text-ink-3">
            <span>Refreshed {fmtDateTime(data.generatedAt)} from {data.org.alias}. Published journeys and active Data Cloud metadata only.</span>
            <span>Quanata · internal</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
