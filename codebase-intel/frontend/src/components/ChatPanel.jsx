/**
 * ChatPanel: RAG-based code Q&A with source citations.
 */
import React, { useState, useRef, useEffect } from 'react'
import { sendChatMessage } from '../api/client.js'
import { Loading, Empty } from './States.jsx'

export default function ChatPanel({ repoId, onCitationClick }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [llmConfigured, setLlmConfigured] = useState(true) // optimistic
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const q = input.trim()
    if (!q || sending) return
    setInput('')
    setSending(true)

    const userMsg = { role: 'user', content: q, sources: [] }
    setMessages((prev) => [...prev, userMsg])

    const history = messages.slice(-12).map((m) => ({ role: m.role, content: m.content }))

    try {
      const result = await sendChatMessage(repoId, q, history)
      setLlmConfigured(result.llm_configured)
      const assistantMsg = {
        role: 'assistant',
        content: result.answer,
        sources: result.sources || [],
        model: result.model,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${e.message}`, sources: [] },
      ])
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      <div className="section-header" style={{ flexShrink: 0 }}>
        <h2>Chat</h2>
        {!llmConfigured && (
          <span style={{ fontSize: 11, color: 'var(--warning)' }}>No LLM key</span>
        )}
      </div>

      {!llmConfigured && (
        <div className="no-llm-notice">
          No LLM API key is configured. Showing the most relevant code sections instead.
          Set <code>OPENAI_API_KEY</code> or <code>ANTHROPIC_API_KEY</code> for AI answers.
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <Empty icon="💬" message="Ask a question about the codebase." />
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
            {msg.sources && msg.sources.length > 0 && (
              <div className="chat-sources">
                {msg.sources.map((s, j) => (
                  <span
                    key={j}
                    className="source-chip"
                    title={s.snippet}
                    onClick={() => onCitationClick && onCitationClick(s)}
                  >
                    {`${s.file_path.split('/').pop()}:${s.start_line}`}
                    {s.related && <span style={{ color: 'var(--muted)', marginLeft: 2 }}> (related)</span>}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="chat-message assistant">
            <Loading message="Thinking…" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          placeholder="Ask about the code… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button className="primary" onClick={handleSend} disabled={sending || !input.trim()}>
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
