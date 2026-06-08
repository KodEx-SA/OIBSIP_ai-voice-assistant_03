'use client'
import { useEffect, useRef, useState } from 'react'
import { supabase, Message, Session } from '@/lib/supabase'

interface Props { session: Session | null }

export default function ConversationPanel({ session }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!session) { setMessages([]); return }

    supabase
      .from('messages')
      .select('*')
      .eq('session_id', session.id)
      .order('created_at', { ascending: true })
      .then(({ data }) => data && setMessages(data))

    const channel = supabase
      .channel(`messages-${session.id}`)
      .on('postgres_changes', {
        event:  'INSERT',
        schema: 'public',
        table:  'messages',
        filter: `session_id=eq.${session.id}`,
      }, (payload) => {
        setMessages((prev) => [...prev, payload.new as Message])
      })
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [session?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fmt = (iso: string) =>
    new Date(iso).toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const roleLabel = (role: string) => {
    if (role === 'user')      return { label: 'USR', cls: 'tag-user' }
    if (role === 'assistant') return { label: 'CLR', cls: 'tag-assistant' }
    return                           { label: 'SYS', cls: 'tag-system' }
  }

  return (
    <div className="panel flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="font-display text-xs tracking-widest text-cyan glow-cyan">CONVERSATION</span>
        {session
          ? <span className="text-xs text-muted truncate max-w-[180px]">{session.room_id}</span>
          : <span className="text-xs text-muted">select a session</span>
        }
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!session && (
          <div className="flex items-center justify-center h-32 text-xs text-muted">
            ← select a session to view transcript
          </div>
        )}
        {session && messages.length === 0 && (
          <div className="flex items-center justify-center h-32 text-xs text-muted">
            no messages recorded
          </div>
        )}
        {messages.map((m) => {
          const { label, cls } = roleLabel(m.role)
          return (
            <div key={m.id} className="group">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-bold ${cls}`}>[{label}]</span>
                <span className="text-xs text-muted">{fmt(m.created_at)}</span>
              </div>
              <p className="text-xs text-[#8baabf] leading-relaxed pl-8 border-l border-border">
                {m.content}
              </p>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
