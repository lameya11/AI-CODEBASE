/**
 * DashboardPage: main analysis view with all panels.
 */
import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getRepo, listFiles } from '../api/client.js'
import Header from '../components/Header.jsx'
import StatsCards from '../components/StatsCards.jsx'
import FileExplorer from '../components/FileExplorer.jsx'
import FileDetail from '../components/FileDetail.jsx'
import GraphView from '../components/GraphView.jsx'
import ImpactPanel from '../components/ImpactPanel.jsx'
import IssuesPanel from '../components/IssuesPanel.jsx'
import ChatPanel from '../components/ChatPanel.jsx'
import { Loading, ErrorBox } from '../components/States.jsx'

const TABS = ['Graph', 'Issues', 'Chat']

export default function DashboardPage() {
  const { repoId } = useParams()
  const [repo, setRepo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null) // { id, path }
  const [selectedNode, setSelectedNode] = useState(null) // file path
  const [highlightLines, setHighlightLines] = useState(null)
  const [affectedPaths, setAffectedPaths] = useState([])
  const [rightTab, setRightTab] = useState('Chat')
  const [centerTab, setCenterTab] = useState('Graph')
  const [allFiles, setAllFiles] = useState([])

  useEffect(() => {
    Promise.all([getRepo(repoId), listFiles(repoId)])
      .then(([r, f]) => { setRepo(r); setAllFiles(f) })
      .catch(setError)
      .finally(() => setLoading(false))
  }, [repoId])

  if (loading) return <Loading message="Loading repository…" />
  if (error) return <ErrorBox error={error} />
  if (!repo) return null

  const handleFileSelect = (file) => {
    setSelectedFile(file)
    setSelectedNode(file.path)
    setHighlightLines(null)
  }

  const handleNodeClick = (nodeId) => {
    // nodeId is a file path
    setSelectedNode(nodeId)
    const file = allFiles.find((f) => f.path === nodeId)
    if (file) setSelectedFile(file)
  }

  const handleCitationClick = (source) => {
    // source has {file_path, start_line, end_line}
    const file = allFiles.find((f) => f.path === source.file_path)
    if (file) {
      setSelectedFile(file)
      setHighlightLines([source.start_line, source.end_line])
      setCenterTab('Files') // show file detail
    }
  }

  const handleIssueClick = (issue) => {
    const file = allFiles.find((f) => f.id === issue.file_id)
    if (file) {
      setSelectedFile(file)
      setHighlightLines([issue.line, issue.line])
      setCenterTab('Files')
    }
  }

  return (
    <div className="layout">
      <Header repo={repo} onReanalyzed={() => window.location.reload()} />
      <StatsCards repoId={repoId} />

      <div className="main-content">
        {/* Left: file explorer */}
        <FileExplorer
          repoId={repoId}
          selectedFileId={selectedFile?.id}
          onFileSelect={handleFileSelect}
        />

        {/* Center: tabs for graph/files */}
        <div className="center-content">
          {/* Tab bar */}
          <div className="tabs" style={{ padding: '0 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
            {['Files', 'Graph'].map((t) => (
              <div
                key={t}
                className={`tab ${centerTab === t ? 'active' : ''}`}
                onClick={() => setCenterTab(t)}
              >
                {t}
              </div>
            ))}
          </div>

          <div style={{ flex: 1, overflow: 'hidden' }}>
            {centerTab === 'Files' ? (
              <div style={{ height: '100%', overflowY: 'auto' }}>
                <FileDetail
                  repoId={repoId}
                  fileId={selectedFile?.id}
                  highlightLines={highlightLines}
                  onCitationClick={(fileId, lines) => {
                    const file = allFiles.find((f) => f.id === fileId)
                    if (file) { setSelectedFile(file); setHighlightLines(lines) }
                  }}
                />
              </div>
            ) : (
              <GraphView
                repoId={repoId}
                selectedNodeId={selectedNode}
                onNodeClick={handleNodeClick}
                affectedPaths={affectedPaths}
              />
            )}
          </div>
        </div>

        {/* Right: chat/impact/issues tabs */}
        <div className="right-panel">
          <div className="tabs" style={{ padding: '0 12px', borderBottom: '1px solid var(--border)' }}>
            {TABS.map((t) => (
              <div
                key={t}
                className={`tab ${rightTab === t ? 'active' : ''}`}
                onClick={() => setRightTab(t)}
              >
                {t}
              </div>
            ))}
          </div>

          <div style={{ height: 'calc(100% - 40px)', overflow: 'hidden' }}>
            {rightTab === 'Chat' && (
              <ChatPanel repoId={repoId} onCitationClick={handleCitationClick} />
            )}
            {rightTab === 'Graph' && (
              <ImpactPanel
                repoId={repoId}
                selectedFilePath={selectedNode}
                onAffectedChange={setAffectedPaths}
              />
            )}
            {rightTab === 'Issues' && (
              <IssuesPanel repoId={repoId} onIssueClick={handleIssueClick} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
