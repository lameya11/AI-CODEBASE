/**
 * Tests for ChatPanel component.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ChatPanel from '../src/components/ChatPanel.jsx'
import * as client from '../src/api/client.js'

vi.mock('../src/api/client.js')

const MOCK_RESPONSE_NO_LLM = {
  answer: 'No LLM API key is configured. Showing the most relevant code sections instead.',
  sources: [
    {
      file_path: 'app/auth.py',
      start_line: 5,
      end_line: 20,
      symbol_name: 'login',
      snippet: 'def login(username, password):',
      score: 0.9,
      related: false,
    },
  ],
  model: null,
  llm_configured: false,
}

const MOCK_RESPONSE_WITH_LLM = {
  answer: 'The login function in auth.py handles authentication. See [app/auth.py:5-20].',
  sources: [
    {
      file_path: 'app/auth.py',
      start_line: 5,
      end_line: 20,
      symbol_name: 'login',
      snippet: 'def login(username, password):',
      score: 0.9,
      related: false,
    },
  ],
  model: 'gpt-4o-mini',
  llm_configured: true,
}

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the chat input', () => {
    render(<ChatPanel repoId="test-repo" />)
    expect(screen.getByPlaceholderText(/Ask about the code/)).toBeInTheDocument()
  })

  it('renders send button', () => {
    render(<ChatPanel repoId="test-repo" />)
    expect(screen.getByText('Send')).toBeInTheDocument()
  })

  it('shows no-LLM notice when llm_configured is false', async () => {
    client.sendChatMessage.mockResolvedValue(MOCK_RESPONSE_NO_LLM)
    render(<ChatPanel repoId="test-repo" />)

    const input = screen.getByPlaceholderText(/Ask about the code/)
    fireEvent.change(input, { target: { value: 'How does login work?' } })
    fireEvent.click(screen.getByText('Send'))

    await waitFor(() => {
      // The no-llm-notice div should appear (there may also be answer text with same words)
      const notices = screen.getAllByText(/No LLM API key/)
      expect(notices.length).toBeGreaterThan(0)
    })
  })

  it('renders source chips from response', async () => {
    client.sendChatMessage.mockResolvedValue(MOCK_RESPONSE_NO_LLM)
    render(<ChatPanel repoId="test-repo" />)

    const input = screen.getByPlaceholderText(/Ask about the code/)
    fireEvent.change(input, { target: { value: 'login?' } })
    fireEvent.click(screen.getByText('Send'))

    await waitFor(() => {
      // Source chip for auth.py:5
      expect(screen.getByText(/auth\.py:5/)).toBeInTheDocument()
    })
  })

  it('calls onCitationClick when source chip is clicked', async () => {
    client.sendChatMessage.mockResolvedValue(MOCK_RESPONSE_WITH_LLM)
    const onCitation = vi.fn()
    render(<ChatPanel repoId="test-repo" onCitationClick={onCitation} />)

    const input = screen.getByPlaceholderText(/Ask about the code/)
    fireEvent.change(input, { target: { value: 'login?' } })
    fireEvent.click(screen.getByText('Send'))

    await waitFor(() => {
      // Use getAllByText and find the source chip specifically
      const chips = screen.getAllByText(/auth\.py:5/).filter(
        el => el.classList.contains('source-chip')
      )
      expect(chips.length).toBeGreaterThan(0)
      fireEvent.click(chips[0])
      expect(onCitation).toHaveBeenCalledWith(expect.objectContaining({
        file_path: 'app/auth.py',
        start_line: 5,
      }))
    })
  })

  it('adds user message to the chat immediately', async () => {
    client.sendChatMessage.mockResolvedValue(MOCK_RESPONSE_WITH_LLM)
    render(<ChatPanel repoId="test-repo" />)

    const input = screen.getByPlaceholderText(/Ask about the code/)
    fireEvent.change(input, { target: { value: 'How does auth work?' } })
    fireEvent.click(screen.getByText('Send'))

    // User message should appear immediately
    expect(screen.getByText('How does auth work?')).toBeInTheDocument()
  })
})
