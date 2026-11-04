/**
 * ImportPage: GitHub URL and ZIP upload tabs with status polling.
 */
import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { createRepoFromGitHub, createRepoFromZip, getRepo } from '../api/client.js'

export default function ImportPage() {
  const [tab, setTab] = useState('github')
  const [githubUrl, setGithubUrl] = useState('')
  const [zipFile, setZipFile] = useState(null)
  const [repoName, setRepoName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusRepo, setStatusRepo] = useState(null)
  const navigate = useNavigate()
  const pollRef = useRef(null)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const validateGitHub = (url) => {
    const re = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/
    return re.test(url)
  }

  const startPolling = (repoId) => {
    pollRef.current = setInterval(async () => {
      try {
        const repo = await getRepo(repoId)
        setStatusRepo(repo)
        if (repo.status === 'ready') {
          clearInterval(pollRef.current)
          navigate(`/dashboard/${repoId}`)
        } else if (repo.status === 'failed') {
          clearInterval(pollRef.current)
          setError(repo.error || 'Ingestion failed')
          setLoading(false)
        }
      } catch (e) {
        clearInterval(pollRef.current)
        setError(e.message)
        setLoading(false)
      }
    }, 2000)
  }

  const handleGitHubSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!validateGitHub(githubUrl)) {
      setError('Please enter a valid GitHub URL (https://github.com/owner/repo)')
      return
    }
    setLoading(true)
    try {
      const repo = await createRepoFromGitHub(githubUrl, repoName || undefined)
      setStatusRepo(repo)
      startPolling(repo.id)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const handleZipSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!zipFile) {
      setError('Please select a ZIP file')
      return
    }
    setLoading(true)
    try {
      const repo = await createRepoFromZip(zipFile, repoName || undefined)
      setStatusRepo(repo)
      startPolling(repo.id)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const statusLabel = (status) => {
    const labels = {
      queued: 'Queued…',
      cloning: 'Cloning repository…',
      parsing: 'Parsing source files…',
      graph_building: 'Building dependency graph…',
      indexing: 'Building vector index…',
      ready: 'Ready!',
      failed: 'Failed',
    }
    return labels[status] || status
  }

  return (
    <div className="import-page">
      <h1>Codebase Intelligence</h1>
      <p className="subtitle">
        Analyze any GitHub repo or ZIP archive — ask questions, explore dependencies, detect issues.
      </p>

      <div className="tabs">
        <div
          className={`tab ${tab === 'github' ? 'active' : ''}`}
          onClick={() => setTab('github')}
        >
          GitHub URL
        </div>
        <div
          className={`tab ${tab === 'zip' ? 'active' : ''}`}
          onClick={() => setTab('zip')}
        >
          Upload ZIP
        </div>
      </div>

      {tab === 'github' && (
        <form onSubmit={handleGitHubSubmit}>
          <div className="form-group">
            <label>GitHub Repository URL</label>
            <input
              type="url"
              placeholder="https://github.com/owner/repo"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label>Name (optional)</label>
            <input
              type="text"
              placeholder="My Project"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
              disabled={loading}
            />
          </div>
          {error && <div className="form-error">{error}</div>}
          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Importing…' : 'Analyze'}
          </button>
        </form>
      )}

      {tab === 'zip' && (
        <form onSubmit={handleZipSubmit}>
          <div className="form-group">
            <label>ZIP File</label>
            <input
              type="file"
              accept=".zip"
              onChange={(e) => setZipFile(e.target.files[0])}
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label>Name (optional)</label>
            <input
              type="text"
              placeholder="My Project"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
              disabled={loading}
            />
          </div>
          {error && <div className="form-error">{error}</div>}
          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Importing…' : 'Analyze'}
          </button>
        </form>
      )}

      {statusRepo && (
        <div className="status-step">
          {statusRepo.status !== 'ready' && statusRepo.status !== 'failed' && (
            <span className="spinner" />
          )}
          <strong>Status:</strong> {statusLabel(statusRepo.status)}
          {statusRepo.status_message && (
            <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
              {statusRepo.status_message}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
