'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

export default function StatsBar() {
  const [stats, setStats] = useState({ sessions: 0, messages: 0, tools: 0, memories: 0, live: 0 })
  const [tick,  setTick]  = useState(0)

  const load = async () => {
    const [s, m, t, mem, live] = await Promise.all([
      supabase.from('sessions').select('id', { count: 'exact', head: true }),
      supabase.from('messages').select('id', { count: 'exact', head: true }),
      supabase.from('tool_executions').select('id', { count: 'exact', head: true }),
      supabase.from('memories').select('key', { count: 'exact', head: true }),
      supabase.from('sessions').select('id', { count: 'exact', head: true }).is('ended_at', null),
    ])
    setStats({
      sessions:  s.count  ?? 0,
      messages:  m.count  ?? 0,
      tools:     t.count  ?? 0,
      memories:  mem.count ?? 0,
      live:      live.count ?? 0,
    })
  }

  useEffect(() => { load() }, [])

  // Tick clock every second
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const now = new Date().toLocaleTimeString('en-ZA', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })

  const stat = (label: string, value: number, color = 'text-cyan', glow = 'glow-cyan') => (
    <div className="flex flex-col items-center">
      <span className={`font-display text-lg font-bold ${color} ${glow}`}>{value}</span>
      <span className="text-xs text-muted tracking-widest">{label}</span>
    </div>
  )

  return (
    <header className="border-b border-border bg-surface px-6 py-3 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-cyan animate-pulse-slow" />
        <span className="font-display text-sm tracking-widest text-cyan glow-cyan animate-flicker">
          CLARE // MISSION CONTROL
        </span>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-8">
        {stat('SESSIONS',  stats.sessions,  'text-cyan',  'glow-cyan')}
        {stat('MESSAGES',  stats.messages,  'text-cyan',  'glow-cyan')}
        {stat('TOOL CALLS',stats.tools,     'text-amber', 'glow-amber')}
        {stat('MEMORIES',  stats.memories,  'text-green', 'glow-green')}
        <div className="flex flex-col items-center">
          <span className={`font-display text-lg font-bold glow-green ${stats.live > 0 ? 'text-green animate-pulse' : 'text-muted'}`}>
            {stats.live}
          </span>
          <span className="text-xs text-muted tracking-widest">LIVE</span>
        </div>
      </div>

      {/* Clock */}
      <span className="font-mono text-xs text-muted tracking-widest">{now}</span>
    </header>
  )
}
