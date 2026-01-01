import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "ContrarianAI | Mission Control",
  description: "AI-powered cryptocurrency trading platform with contrarian sentiment analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased bg-zinc-950 text-zinc-100`}
      >
        {children}
        <Toaster
          theme="dark"
          position="top-right"
          toastOptions={{
            style: {
              background: '#18181b',  // zinc-900
              border: '1px solid #27272a',  // zinc-800
              color: '#f4f4f5',  // zinc-100
            },
          }}
        />
      </body>
    </html>
  );
}
