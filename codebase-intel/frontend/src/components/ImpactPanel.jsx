/**
 * ImpactPanel: analyze and display the impact of changing a file.
 */
import React, { useState } from 'react'
import { analyzeImpact } from '../api/client.js'
import { Loading, ErrorBox, Empty } from './States.jsx'

export default function ImpactPanel({ repoId, selectedFilePath, onAffectedChange }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    if (!selectedFilePath) return
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeImpact(repoId, selectedFilePath)
      setResult(data)
      if (onAffectedChange) onAffectedChange(data.affected_paths)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  const depthClass = (depth) => {
    if (depth === 1) return 'depth-1'
    if (depth === 2) return 'depth-2'
    return 'depth-3plus'
  }

  return (
    <div style={{ padding: 12 }}>
      <div className="section-header" style={{ padding: '0 0 10px 0' }}>
        <h2>Impact Analysis</h2>
      </div>

      {!selectedFilePath && (
        <Empty icon="🎯" message="Select a file in the graph or explorer to analyze impact." />
      )}

      {selectedFilePath && (
        <>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
            Target: <code>{selectedFilePath}</code>
          </div>
          <button className="primary" onClick={handleAnalyze} disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Analyzing…' : 'Analyze Impact'}
          </button>
        </>
      )}

      {loading && <Loading message="Analyzing dependencies…" />}
      {error && <ErrorBox error={error} />}

      {result && !loading && (
        <div className="impact-panel">
          <div className={`impact-level ${result.level}`}>
            {result.level.toUpperCase()} IMPACT
          </div>
          <p style={{ fontSize: 13, marginBottom: 10 }}>
            {result.explanation}
          </p>

          {result.direct.length > 0 && (
            <>
              <h4 style={{ fontSize: 12, marginBottom: 4 }}>Direct ({result.direct.length})</h4>
              <ul className="affected-list" style={{ marginBottom: 10 }}>
                {result.direct.map((d) => (
                  <li key={d.file_path} className={`affected-item ${depthClass(d.depth)}`}>
                    {d.file_path.split('/').pop()}
                    <span style={{ color: 'var(--muted)', fontSize: 10, marginLeft: 4 }}>
                      {d.file_path}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {result.indirect.length > 0 && (
            <>
              <h4 style={{ fontSize: 12, marginBottom: 4 }}>Indirect ({result.indirect.length})</h4>
              <ul className="affected-list" style={{ marginBottom: 10 }}>
                {result.indirect.map((d) => (
                  <li key={d.file_path} className={`affected-item ${depthClass(d.depth)}`}>
                    {d.file_path.split('/').pop()}
                    <span style={{ color: 'var(--muted)', fontSize: 10, marginLeft: 4 }}>
                      {d.file_path}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="disclaimer">{result.disclaimer}</div>
        </div>
      )}
    </div>
  )
}
