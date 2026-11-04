/**
 * FileExplorer: collapsible tree built from flat file list with search.
 */
import React, { useEffect, useState, useMemo } from 'react'
import { listFiles } from '../api/client.js'
import { Loading, ErrorBox, Empty } from './States.jsx'

function buildTree(files) {
  /**
   * Build a nested tree from flat file paths.
   * Each directory node: { _files: [], _dirs: { name: dirNode } }
   */
  const root = { _files: [], _dirs: {} }
  for (const file of files) {
    const parts = file.path.split('/')
    let node = root
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i]
      if (!node._dirs[part]) node._dirs[part] = { _files: [], _dirs: {} }
      node = node._dirs[part]
    }
    node._files.push(file)
  }
  return root
}

function TreeDir({ name, node, depth, selectedId, onSelect, filterText }) {
  const [open, setOpen] = useState(depth < 3)

  const files = (node._files || []).filter(
    (f) => !filterText || f.path.toLowerCase().includes(filterText.toLowerCase())
  )

  const subdirs = Object.entries(node._dirs || {})

  // When filtering, only show if this dir or any subdir has matching content
  const hasContent = files.length > 0 || subdirs.some(([, sub]) =>
    JSON.stringify(sub).toLowerCase().includes((filterText || '').toLowerCase())
  )
  if (filterText && !hasContent) return null

  return (
    <div>
      {name && (
        <div
          className="tree-node tree-folder"
          style={{ paddingLeft: depth * 12 + 8 }}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="icon">{open ? '📂' : '📁'}</span>
          {name}
        </div>
      )}
      {(open || !name) && (
        <>
          {files.map((f) => (
            <div
              key={f.id}
              className={`tree-node ${selectedId === f.id ? 'selected' : ''} ${!f.supported ? 'unsupported' : ''}`}
              style={{ paddingLeft: (depth + 1) * 12 + 8 }}
              onClick={() => onSelect(f)}
              title={f.path}
            >
              <span className="icon">{getFileIcon(f.language)}</span>
              {f.path.split('/').pop()}
              {f.issue_count > 0 && (
                <span style={{ marginLeft: 4, fontSize: 10, color: 'var(--danger)' }} data-testid="issue-badge">
                  !{f.issue_count}
                </span>
              )}
            </div>
          ))}
          {subdirs.map(([dirName, dirNode]) => (
            <TreeDir
              key={dirName}
              name={dirName}
              node={dirNode}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              filterText={filterText}
            />
          ))}
        </>
      )}
    </div>
  )
}

function getFileIcon(language) {
  const icons = {
    python: '🐍',
    javascript: '🟡',
    typescript: '🔷',
  }
  return icons[language] || '📄'
}

export default function FileExplorer({ repoId, onFileSelect, selectedFileId }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    listFiles(repoId)
      .then(setFiles)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [repoId])

  const tree = useMemo(() => {
    const filtered = search
      ? files.filter((f) => f.path.toLowerCase().includes(search.toLowerCase()))
      : files
    return buildTree(filtered)
  }, [files, search])

  if (loading) return <Loading message="Loading files…" />
  if (error) return <ErrorBox error={error} />
  if (files.length === 0) return <Empty icon="📂" message="No files found." />

  return (
    <div className="sidebar">
      <div className="file-tree-search">
        <input
          placeholder="Filter files…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="file-tree">
        <TreeDir
          name=""
          node={tree}
          depth={0}
          selectedId={selectedFileId}
          onSelect={onFileSelect}
          filterText={search}
        />
      </div>
    </div>
  )
}
