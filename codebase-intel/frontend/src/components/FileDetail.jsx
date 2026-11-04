/**
 * FileDetail: symbols, imports, issues, and source code viewer.
 */
import React, { useEffect, useState } from 'react'
import { getFile, getFileContent } from '../api/client.js'
import { Loading, ErrorBox, Empty } from './States.jsx'

const KIND_COLORS = {
  route: 'route',
  component: 'component',
  function: 'function',
  class: 'class',
  method: 'function',
}

export default function FileDetail({ repoId, fileId, highlightLines, onCitationClick }) {
  const [fileData, setFileData] = useState(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!fileId) return
    setLoading(true)
    setError(null)

    Promise.all([
      getFile(repoId, fileId),
      getFileContent(repoId, fileId),
    ])
      .then(([fd, fc]) => {
        setFileData(fd)
        setContent(typeof fc === 'object' ? fc.content : fc)
      })
      .catch(setError)
      .finally(() => setLoading(false))
  }, [repoId, fileId])

  if (!fileId) return <Empty icon="📄" message="Select a file to view details." />
  if (loading) return <Loading message="Loading file…" />
  if (error) return <ErrorBox error={error} />
  if (!fileData) return null

  const lines = content ? content.split('\n') : []
  const highlightSet = new Set(
    highlightLines
      ? Array.from({ length: highlightLines[1] - highlightLines[0] + 1 }, (_, i) => highlightLines[0] + i)
      : []
  )

  return (
    <div className="file-detail">
      <h2 style={{ fontFamily: 'monospace' }}>{fileData.path}</h2>

      {/* Symbols */}
      {fileData.symbols.length > 0 && (
        <div className="section">
          <h3>Symbols</h3>
          <div>
            {fileData.symbols.map((sym) => (
              <span
                key={sym.id}
                className={`symbol-chip ${KIND_COLORS[sym.kind] || 'function'}`}
                title={`${sym.kind} ${sym.name} (L${sym.start_line}–${sym.end_line})`}
              >
                {sym.kind === 'route' ? `${sym.route_method} ${sym.route_path}` : sym.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Imports */}
      {fileData.imports.length > 0 && (
        <div className="section">
          <h3>Imports</h3>
          <div style={{ fontSize: 12 }}>
            {fileData.imports.slice(0, 20).map((imp, i) => (
              <div key={i} style={{ padding: '2px 0' }}>
                <code style={{ color: imp.is_external ? 'var(--muted)' : 'var(--accent)' }}>
                  {imp.target_module}
                </code>
                {imp.resolved_path && (
                  <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 4 }}>
                    → {imp.resolved_path}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Issues */}
      {fileData.issues.length > 0 && (
        <div className="section">
          <h3>Issues</h3>
          {fileData.issues.map((iss) => (
            <div key={iss.id} className={`issue-item ${iss.severity}`}>
              <div className="type-badge">{iss.type.replace('_', ' ').toUpperCase()}</div>
              <div className="message">{iss.message}</div>
              <div
                className="location"
                onClick={() => onCitationClick && onCitationClick(fileData.id, [iss.line, iss.line])}
              >
                Line {iss.line}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Source code */}
      {content && (
        <div className="code-viewer">
          <pre>
            {lines.map((line, i) => {
              const lineNo = i + 1
              return (
                <div
                  key={lineNo}
                  className={`code-line ${highlightSet.has(lineNo) ? 'highlighted' : ''}`}
                >
                  <span className="lineno">{lineNo}</span>
                  <span>{line}</span>
                </div>
              )
            })}
          </pre>
        </div>
      )}
    </div>
  )
}
