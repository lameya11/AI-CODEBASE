/**
 * GraphView: React Flow graph of the dependency graph.
 */
import React, { useEffect, useState, useCallback, useMemo, lazy, Suspense } from 'react'
import { getGraph } from '../api/client.js'
import { Loading, ErrorBox, Empty } from './States.jsx'

const FOLDER_COLORS = [
  '#dbeafe', '#dcfce7', '#fef3c7', '#ede9fe', '#fce7f3',
  '#e0f2fe', '#d1fae5', '#fef9c3', '#f3e8ff', '#ffedd5',
]

function getFolderColor(folder, folderMap) {
  if (!folderMap.has(folder)) {
    folderMap.set(folder, FOLDER_COLORS[folderMap.size % FOLDER_COLORS.length])
  }
  return folderMap.get(folder)
}

function SimpleGraphFallback({ nodes, edges, selectedNodeId, onNodeClick, affectedPaths }) {
  const affectedSet = new Set(affectedPaths || [])
  return (
    <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {nodes.filter(n => !n.data?.is_external).map((n) => (
          <div
            key={n.id}
            style={{
              padding: '4px 10px',
              borderRadius: 6,
              fontSize: 12,
              background: affectedSet.has(n.id) ? '#fef3c7' : (n.id === selectedNodeId ? '#dbeafe' : 'var(--surface)'),
              border: '1px solid var(--border)',
              cursor: 'pointer',
            }}
            onClick={() => onNodeClick && onNodeClick(n.id)}
          >
            {n.data?.label || n.id.split('/').pop()}
          </div>
        ))}
      </div>
      <p style={{ marginTop: 12, fontSize: 11, color: 'var(--muted)' }}>
        {edges.length} dependencies found
      </p>
    </div>
  )
}

// Lazy-load ReactFlow to keep it optional
const ReactFlowGraph = lazy(() =>
  import('@xyflow/react').then((mod) => ({
    default: function FlowWrapper({ nodes, edges, onNodeClick }) {
      const { ReactFlow, Controls, Background } = mod
      return (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodeClick={(_, node) => onNodeClick && onNodeClick(node.id)}
          fitView
          minZoom={0.2}
        >
          <Controls />
          <Background />
        </ReactFlow>
      )
    },
  })).catch(() => ({
    default: function Fallback() {
      return <div style={{ padding: 16, color: 'var(--muted)', fontSize: 12 }}>
        Install @xyflow/react for interactive graph
      </div>
    }
  }))
)

export default function GraphView({ repoId, selectedNodeId, onNodeClick, affectedPaths }) {
  const [graphData, setGraphData] = useState(null)
  const [level, setLevel] = useState('file')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const folderColorMap = useMemo(() => new Map(), [repoId])

  useEffect(() => {
    setLoading(true)
    setError(null)
    getGraph(repoId, level)
      .then(setGraphData)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [repoId, level])

  if (loading) return <Loading message="Loading graph…" />
  if (error) return <ErrorBox error={error} />
  if (!graphData || graphData.nodes.length === 0) return <Empty icon="🕸️" message="No graph data yet." />

  const affectedSet = new Set(affectedPaths || [])

  const flowNodes = graphData.nodes.map((n, idx) => ({
    id: n.id,
    position: {
      x: (idx % 8) * 180,
      y: Math.floor(idx / 8) * 100,
    },
    data: { label: n.label, is_external: n.is_external, folder: n.folder },
    style: {
      background: affectedSet.has(n.id)
        ? '#fef3c7'
        : n.id === selectedNodeId
        ? '#dbeafe'
        : n.is_external
        ? '#f3f4f6'
        : getFolderColor(n.folder || '/', folderColorMap),
      border: `1px solid ${n.id === selectedNodeId ? '#3b82d4' : '#e5e7eb'}`,
      borderRadius: 6,
      fontSize: 11,
      padding: '4px 8px',
      opacity: n.is_external ? 0.6 : 1,
    },
  }))

  const flowEdges = graphData.edges.map((e, idx) => ({
    id: `e${idx}`,
    source: e.source,
    target: e.target,
    style: { stroke: '#d1d5db', strokeWidth: 1 },
    markerEnd: { type: 'arrowclosed', color: '#d1d5db' },
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
        <button
          className={level === 'file' ? 'primary' : ''}
          onClick={() => setLevel('file')}
          style={{ fontSize: 12, padding: '3px 10px' }}
        >
          File
        </button>
        <button
          className={level === 'function' ? 'primary' : ''}
          onClick={() => setLevel('function')}
          style={{ fontSize: 12, padding: '3px 10px' }}
        >
          Function
        </button>
        <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 8 }}>
          {graphData.nodes.length} nodes · {graphData.edges.length} edges
        </span>
      </div>

      {/* Legend */}
      <div className="graph-legend">
        <div className="legend-item">
          <div className="legend-dot" style={{ background: '#dbeafe' }} />
          <span>Selected</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: '#fef3c7' }} />
          <span>Affected</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: '#f3f4f6' }} />
          <span>External</span>
        </div>
      </div>

      {/* Graph */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Suspense fallback={<Loading message="Loading graph…" />}>
          <ReactFlowGraph
            nodes={flowNodes}
            edges={flowEdges}
            onNodeClick={onNodeClick}
          />
        </Suspense>
        {/* Fallback for when ReactFlow is not available - show simple view */}
        <noscript>
          <SimpleGraphFallback
            nodes={flowNodes}
            edges={flowEdges}
            selectedNodeId={selectedNodeId}
            onNodeClick={onNodeClick}
            affectedPaths={affectedPaths}
          />
        </noscript>
      </div>
    </div>
  )
}
