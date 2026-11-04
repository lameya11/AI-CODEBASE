/**
 * Tests for FileExplorer component.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FileExplorer from '../src/components/FileExplorer.jsx'
import * as client from '../src/api/client.js'

vi.mock('../src/api/client.js')

const MOCK_FILES = [
  { id: 1, path: 'backend/app/main.py', language: 'python', line_count: 50, size: 1200, supported: true, parse_error: null, issue_count: 0 },
  { id: 2, path: 'backend/app/auth.py', language: 'python', line_count: 30, size: 800, supported: true, parse_error: null, issue_count: 1 },
  { id: 3, path: 'frontend/src/App.jsx', language: 'javascript', line_count: 20, size: 500, supported: true, parse_error: null, issue_count: 0 },
  { id: 4, path: 'README.md', language: null, line_count: 10, size: 200, supported: false, parse_error: null, issue_count: 0 },
]

describe('FileExplorer', () => {
  beforeEach(() => {
    client.listFiles.mockResolvedValue(MOCK_FILES)
  })

  it('renders files after loading', async () => {
    render(<FileExplorer repoId="test-repo" onFileSelect={() => {}} />)
    // Wait for files to load
    const mainPy = await screen.findByText('main.py')
    expect(mainPy).toBeInTheDocument()
  })

  it('shows nested tree structure', async () => {
    render(<FileExplorer repoId="test-repo" onFileSelect={() => {}} />)
    await screen.findByText('main.py')
    // Should show directory names
    expect(screen.getByText('backend')).toBeInTheDocument()
  })

  it('filters files by search', async () => {
    render(<FileExplorer repoId="test-repo" onFileSelect={() => {}} />)
    await screen.findByText('main.py')

    const searchInput = screen.getByPlaceholderText('Filter files…')
    fireEvent.change(searchInput, { target: { value: 'auth' } })

    // auth.py should still be visible
    expect(screen.getByText('auth.py')).toBeInTheDocument()
  })

  it('calls onFileSelect when file is clicked', async () => {
    const onSelect = vi.fn()
    render(<FileExplorer repoId="test-repo" onFileSelect={onSelect} />)
    const authFile = await screen.findByText('auth.py')
    fireEvent.click(authFile)
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }))
  })

  it('shows issue count badge', async () => {
    render(<FileExplorer repoId="test-repo" onFileSelect={() => {}} />)
    await screen.findByText('auth.py')
    // auth.py has 1 issue - look for badge
    const badges = screen.getAllByTestId('issue-badge')
    expect(badges.length).toBeGreaterThan(0)
    expect(badges[0].textContent).toContain('1')
  })

  it('shows unsupported files greyed out', async () => {
    render(<FileExplorer repoId="test-repo" onFileSelect={() => {}} />)
    await screen.findByText('README.md')
    const readmeEl = screen.getByText('README.md').closest('.tree-node')
    expect(readmeEl).toHaveClass('unsupported')
  })
})
