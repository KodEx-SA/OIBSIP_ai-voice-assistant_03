import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Clare // Mission Control',
  description: 'Real-time dashboard for Clare voice assistant',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
