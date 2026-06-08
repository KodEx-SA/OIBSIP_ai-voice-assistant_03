'use client'
import { useState } from 'react'
import StatsBar          from '@/components/StatsBar'
import SessionsPanel     from '@/components/SessionsPanel'
import ConversationPanel from '@/components/ConversationPanel'
import ToolLogPanel      from '@/components/ToolLogPanel'
import MemoriesPanel     from '@/components/MemoriesPanel'
import { Session }       from '@/lib/supabase'

export default function Dashboard() {
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [activeTab, setActiveTab] = useState<'conversation' | 'tools' | 'memories'>('conversation')

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <StatsBar />

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-[280px_1fr_1fr] overflow-hidden">

        {/* Column 1 — Sessions */}
        <div className="border-r border-border overflow-hidden flex flex-col">
          <SessionsPanel
            onSelect={setSelectedSession}
            selectedId={selectedSession?.id ?? null}
          />
        </div>

        {/* Column 2 — Conversation */}
        <div className="border-r border-border overflow-hidden flex flex-col">
          <ConversationPanel session={selectedSession} />
        </div>

        {/* Column 3 — Tabbed: Tools | Memories */}
        <div className="overflow-hidden flex flex-col">
          {/* Tab bar */}
          <div className="flex border-b border-border">
            {(['tools', 'memories'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`
                  flex-1 py-3 text-xs tracking-widest font-display transition-colors
                  ${activeTab === tab
                    ? 'text-cyan glow-cyan border-b-2 border-cyan'
                    : 'text-muted hover:text-cyan'
                  }
                `}
              >
                {tab.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-hidden">
            {activeTab === 'tools'    && <ToolLogPanel />}
            {activeTab === 'memories' && <MemoriesPanel />}
          </div>
        </div>
      </div>
    </div>
  )
}
