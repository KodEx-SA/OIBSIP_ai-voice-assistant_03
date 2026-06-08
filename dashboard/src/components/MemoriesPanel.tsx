'use client'
import { useEffect, useState } from 'react'
import { supabase, Memory } from '@/lib/supabase'

export default function MemoriesPanel() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [deleting, setDeleting] = useState<string | null>(null)
  const [confirm, setConfirm]   = useState<string | null>(null)

  const load = () =>
    supabase
      .from('memories')
      .select('key, content, source, updated_at')
      .order('updated_at', { ascending: false })
      .then(({ data }) => data && setMemories(data))

  useEffect(() => {
    load()

    const channel = supabase
      .channel('memories-watch')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'memories' }, load)
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [])

  const handleDelete = async (key: string) => {
    if (confirm !== key) { setConfirm(key); return }
    setDeleting(key)
    await supabase.from('memories').delete().eq('key', key)
    setDeleting(null)
    setConfirm(null)
  }

  const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString('en-ZA', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

  return (
    <div className="panel flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="font-display text-xs tracking-widest text-cyan glow-cyan">LONG-TERM MEMORY</span>
        <span className="text-xs text-muted">{memories.length} stored</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {memories.length === 0 && (
          <div className="flex items-center justify-center h-32 text-xs text-muted">
            no memories stored yet
          </div>
        )}
        {memories.map((m) => (
          <div key={m.key} className="border-b border-border px-4 py-3 hover:bg-dim transition-colors group">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-green glow-green">{m.key}</span>
                  <span className="text-xs text-muted">·</span>
                  <span className="text-xs text-muted">{m.source}</span>
                </div>
                <p className="text-xs text-[#8baabf] leading-relaxed">{m.content}</p>
                <span className="text-xs text-muted mt-1 block">{fmt(m.updated_at)}</span>
              </div>

              {/* Delete */}
              <button
                onClick={() => handleDelete(m.key)}
                disabled={deleting === m.key}
                className={`
                  flex-shrink-0 text-xs px-2 py-1 border rounded transition-all
                  ${confirm === m.key
                    ? 'border-red text-red hover:bg-red/10'
                    : 'border-border text-muted hover:border-red hover:text-red opacity-0 group-hover:opacity-100'
                  }
                `}
              >
                {deleting === m.key ? '...' : confirm === m.key ? 'confirm' : 'del'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
