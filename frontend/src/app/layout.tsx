import type { Metadata, Viewport } from "next"
import { Literata, Manrope } from "next/font/google"
import { AuthGate } from "@/components/auth/AuthGate"
import "./globals.css"

const literata = Literata({
  variable: "--font-serif",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "700"],
  display: "swap",
})

const manrope = Manrope({
  variable: "--font-sans",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
})

export const metadata: Metadata = {
  title: "Энергоинформационная медицина — Г.А. Юсупов",
  description: "Теория и практика энергоинформационной медицины. Веб-читалка с AI-ассистентом",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "ЭИМ Юсупов",
  },
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f6f1" },
    { media: "(prefers-color-scheme: dark)", color: "#0e0e1a" },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body className={`${literata.variable} ${manrope.variable}`}>
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  )
}
