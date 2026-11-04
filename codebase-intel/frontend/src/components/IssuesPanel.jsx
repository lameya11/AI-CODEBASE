/**
 * IssuesPanel: list all issues with filters.
 */
import React, { useEffect, useState } from 'react'
import { listIssues } from '../api/client.js'
import { Loading, ErrorBox, Empty } from './States.jsx'

const ISSUE_TYPES = ['', 'secret', 'sql_injection', 'unused_import', 'complexity']
const SEVERITIES = ['', 'high', 'warning', 'info']

export default function IssuesPanel({ repoId, onIssueClick }) {
  const [issues, setIssues] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [typeFilter, setTypeFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')

  const loadIssues = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listIssues(repoId, typeFilter || undefined, severityFilter || undefined)
      setIssues(data.issues)
      setCounts({ byType: data.counts_by_type, bySeverity: data.counts_by_severity })
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadIssues() }, [repoId, typeFilter, severityFilter])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="section-header">
        <h2>Issues {!loading && `(${issues.length})`}</h2>
      </div>

      <div className="filter-row">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          {ISSUE_TYPES.map((t) => (
            <option key={t} value={t}>{t || 'All types'}</option>
          ))}
        </select>
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s || 'All severities'}</option>
          ))}
        </select>
      </div>

      {loading && <Loading message="Loading issues…" />}
      {error && <ErrorBox error={error} />}

      {!loading && !error && issues.length === 0 && (
        <Empty icon="✅" message="No issues found." />
      )}

      {!loading && !error && issues.length > 0 && (
        <div style={{ overflowY: 'auto', flex: 1, padding: '8px 12px' }}>
          {issues.map((iss) => (
            <div key={iss.id} className={`issue-item ${iss.severity}`}>
              <div className="type-badge">{iss.type.replace('_', ' ').toUpperCase()} · {iss.severity}</div>
              <div className="message">{iss.message}</div>
              <div
                className="location"
                onClick={() => onIssueClick && onIssueClick(iss)}
              >
                {iss.file_path ? iss.file_path.split('/').pop() : '?'}:{iss.line}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
