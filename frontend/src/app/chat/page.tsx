"use client"

import { ArrowLeft, MessageCircle } from "lucide-react"
import Link from "next/link"

export default function ChatPage() {
  return (
    <div className="flex flex-col h-dvh" style={{ background: "var(--bg-primary)" }}>
      <header
        id="chat-header"
        className="flex items-center gap-3 px-4 py-3 border-b shrink-0"
        style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
      >
        <Link href="/" className="p-1 rounded hover:opacity-70">
          <ArrowLeft size={20} strokeWidth={1.25} />
        </Link>
        <MessageCircle size={20} strokeWidth={1.25} style={{ color: "var(--accent)" }} />
        <h1 className="font-medium text-sm" style={{ fontFamily: "var(--font-sans)" }}>
          AI-ассистент
        </h1>
      </header>

      <div className="flex-1 flex items-center justify-center px-8">
        <div className="text-center" style={{ color: "var(--text-muted)" }}>
          <MessageCircle size={48} strokeWidth={1.25} className="mx-auto mb-4 opacity-30" />
          <p className="text-sm mb-2">AI-ассистент по книге</p>
          <p className="text-xs">Задавайте вопросы по содержанию книги — ассистент найдёт ответ и укажет страницы</p>
          <p className="text-xs mt-4 opacity-60">Будет доступен в Phase 5</p>
        </div>
      </div>
    </div>
  )
}
