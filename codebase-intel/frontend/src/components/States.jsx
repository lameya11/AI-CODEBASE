/**
 * Loading, Empty and ErrorBox shared state components.
 */
import React from 'react'

export function Loading({ message = 'Loading...' }) {
  return (
    <div className="state-container">
      <div className="skeleton" style={{ width: 180, marginBottom: 8 }} />
      <div className="skeleton" style={{ width: 120, height: 12 }} />
      <p style={{ marginTop: 12, color: 'var(--muted)', fontSize: 13 }}>{message}</p>
    </div>
  )
}

export function Empty({ icon = '📂', message = 'Nothing here yet.' }) {
  return (
    <div className="state-container">
      <div className="icon">{icon}</div>
      <p>{message}</p>
    </div>
  )
}

export function ErrorBox({ error }) {
  const msg = typeof error === 'string' ? error : (error?.message || 'An error occurred')
  return (
    <div className="state-container">
      <div className="icon">⚠️</div>
      <p style={{ color: 'var(--danger)', maxWidth: 400 }}>{msg}</p>
    </div>
  )
}
