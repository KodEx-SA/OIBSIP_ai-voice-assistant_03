'use client'
import { useEffect, useState } from 'react'
import { supabase, ToolExecution } from '@/lib/supabase'

const TOOL_COLORS: Record<string, string> = {
  get_temperature: 'text-cyan',
  remember:        'text-green',
  recall:          'text-green',
  forget:          'text-amber',
  list_memories:   'text-green',
}

export default function ToolLogPanel() {
  const [execs, setExecs] = useState<ToolExecution[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    supabase
      .from('tool_executions')
      .select('*')
      .order('executed_at', { ascending: false })
      .limit(100)
      .then(({ data }) => data && setExecs(data))

    const channel = supabase
      .channel('tools-watch')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'tool_executions' },
        (payload) => {
          setExecs((prev) => [payload.new as ToolExecution, ...prev].slice(0, 100))
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [])

  const fmt = (iso: string) =>
    new Date(iso).toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className="panel flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="font-display text-xs tracking-widest text-cyan glow-cyan">TOOL EXECUTIONS</span>
        <span className="text-xs text-muted">{execs.length} logged</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {execs.length === 0 && (
          <div className="flex items-center justify-center h-32 text-xs text-muted">
            no tool calls yet
          </div>
        )}
        {execs.map((e) => {
          const color    = TOOL_COLORS[e.tool_name] ?? 'text-[#8baabf]'
          const isOpen   = expanded === e.id
          const hasError = e.status === 'error'
          return (
            <div key={e.id} className="border-b border-border">
              <button
                onClick={() => setExpanded(isOpen ? null : e.id)}
                className="w-full text-left px-4 py-2.5 hover:bg-dim transition-colors flex items-center gap-3"
              >
                {/* Status dot */}
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${hasError ? 'bg-red' : 'bg-green'}`} />
                {/* Tool name */}
                <span className={`text-xs font-bold flex-1 ${color}`}>{e.tool_name}</span>
                {/* Duration */}
                {e.duration_ms != null && (
                  <span className="text-xs text-muted">{e.duration_ms}ms</span>
                )}
                {/* Time */}
                <span className="text-xs text-muted">{fmt(e.executed_at)}</span>
                {/* Expand chevron */}
                <span className={`text-muted text-xs transition-transform ${isOpen ? 'rotate-90' : ''}`}>›</span>
              </button>

              {isOpen && (
                <div className="px-4 pb-3 space-y-2 bg-bg">
                  <div>
                    <span className="text-xs text-muted block mb-1">ARGS</span>
                    <pre className="text-xs text-amber bg-dim p-2 rounded overflow-x-auto">
                      {JSON.stringify(e.arguments, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <span className="text-xs text-muted block mb-1">RESULT</span>
                    <pre className={`text-xs p-2 bg-dim rounded overflow-x-auto ${hasError ? 'text-red' : 'text-green'}`}>
                      {JSON.stringify(e.result, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
