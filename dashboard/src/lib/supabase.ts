import { createClient } from '@supabase/supabase-js'

const url = process.env.NEXT_PUBLIC_SUPABASE_URL!
const key = process.env.NEXT_PUBLIC_SUPABASE_KEY!

export const supabase = createClient(url, key)

// ── Types ────────────────────────────────────────────────────────────────────

export interface Session {
  id:         string
  room_id:    string
  started_at: string
  ended_at:   string | null
  metadata:   Record<string, unknown>
}

export interface Message {
  id:         string
  session_id: string
  role:       'user' | 'assistant' | 'system'
  content:    string
  created_at: string
}

export interface Memory {
  key:        string
  content:    string
  source:     string
  updated_at: string
}

export interface ToolExecution {
  id:          string
  session_id:  string
  tool_name:   string
  arguments:   Record<string, unknown>
  result:      Record<string, unknown>
  status:      'success' | 'error'
  executed_at: string
  duration_ms: number | null
}
