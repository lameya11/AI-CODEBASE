/**
 * Header component with repo name, status badge, and actions.
 */
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { reanalyzeRepo } from '../api/client.js'

export default function Header({ repo, onReanalyzed }) {
  const navigate = useNavigate()

  const handleReanalyze = async () => {
    try {
      await reanalyzeRepo(repo.id)
      if (onReanalyzed) onReanalyzed()
    } catch (e) {
      alert(e.message)
    }
  }

  const formatDate = (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleString()
  }

  return (
    <div className="header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/')} style={{ padding: '4px 8px' }}>← Back</button>
        <h1>{repo.name}</h1>
        <span className={`badge ${repo.status}`}>{repo.status}</span>
        {repo.last_analyzed_at && (
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            Last analyzed: {formatDate(repo.last_analyzed_at)}
          </span>
        )}
      </div>
      <div className="actions">
        {repo.source_type === 'github' && (
          <button onClick={handleReanalyze} disabled={repo.status !== 'ready' && repo.status !== 'failed'}>
            Re-analyze
          </button>
        )}
      </div>
    </div>
  )
}
