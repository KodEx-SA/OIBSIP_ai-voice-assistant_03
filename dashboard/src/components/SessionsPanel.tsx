'use client'
import { useEffect, useState } from 'react'
import { supabase, Session } from '@/lib/supabase'

interface Props {
  onSelect: (session: Session) => void
  selectedId: string | null
}

export default function SessionsPanel({ onSelect, selectedId }: Props) {
  const [sessions, setSessions] = useState<Session[]>([])

  useEffect(() => {
    // Initial fetch
    supabase
      .from('sessions')
      .select('*')
      .order('started_at', { ascending: false })
      .limit(50)
      .then(({ data }) => data && setSessions(data))

    // Realtime subscription
    const channel = supabase
      .channel('sessions-watch')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'sessions' }, () => {
        supabase
          .from('sessions')
          .select('*')
          .order('started_at', { ascending: false })
          .limit(50)
          .then(({ data }) => data && setSessions(data))
      })
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [])

  const fmt = (iso: string) =>
    new Date(iso).toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const duration = (s: Session) => {
    if (!s.ended_at) return null
    const ms = new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()
    return `${Math.round(ms / 1000)}s`
  }

  return (
    <div className="panel flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="font-display text-xs tracking-widest text-cyan glow-cyan">SESSIONS</span>
        <span className="text-xs text-muted">{sessions.length} total</span>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 && (
          <div className="flex items-center justify-center h-32 text-xs text-muted">
            awaiting connections...
          </div>
        )}
        {sessions.map((s) => {
          const active   = !s.ended_at
          const selected = s.id === selectedId
          return (
            <button
              key={s.id}
              onClick={() => onSelect(s)}
              className={`
                w-full text-left px-4 py-3 border-b border-border transition-all
                hover:bg-dim group
                ${selected ? 'bg-dim border-l-2 border-l-cyan' : 'border-l-2 border-l-transparent'}
              `}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {active
                    ? <span className="w-1.5 h-1.5 rounded-full bg-green animate-pulse" />
                    : <span className="w-1.5 h-1.5 rounded-full bg-muted" />
                  }
                  <span className={`text-xs font-mono ${active ? 'text-green glow-green' : 'text-muted'}`}>
                    {active ? 'LIVE' : 'CLOSED'}
                  </span>
                </div>
                <span className="text-xs text-muted">{duration(s) ?? '—'}</span>
              </div>
              <div className="text-xs text-cyan truncate">{s.room_id}</div>
              <div className="text-xs text-muted mt-0.5">{fmt(s.started_at)}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
