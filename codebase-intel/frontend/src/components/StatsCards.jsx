/**
 * Stats cards showing repository metrics.
 */
import React, { useEffect, useState } from 'react'
import { getStats } from '../api/client.js'
import { Loading, ErrorBox } from './States.jsx'

export default function StatsCards({ repoId }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getStats(repoId)
      .then(setStats)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [repoId])

  if (loading) return <div className="stats-grid"><Loading message="Loading stats…" /></div>
  if (error) return <ErrorBox error={error} />
  if (!stats) return null

  const cards = [
    { label: 'Files', value: stats.file_count },
    { label: 'Supported', value: stats.supported_file_count },
    { label: 'Lines', value: stats.line_count?.toLocaleString() },
    { label: 'Functions', value: stats.function_count },
    { label: 'Classes', value: stats.class_count },
    { label: 'Routes', value: stats.route_count },
    { label: 'Components', value: stats.component_count },
    { label: 'Issues', value: stats.issue_count },
  ]

  return (
    <>
      <div className="stats-grid">
        {cards.map((c) => (
          <div key={c.label} className="stat-card">
            <div className="label">{c.label}</div>
            <div className="value">{c.value ?? '—'}</div>
          </div>
        ))}
      </div>
      <div style={{ padding: '4px 16px 8px', fontSize: 11, color: 'var(--muted)' }}>
        Embedder: <strong>{stats.embedder}</strong> · Vector backend: <strong>{stats.vector_backend}</strong>
      </div>
    </>
  )
}
