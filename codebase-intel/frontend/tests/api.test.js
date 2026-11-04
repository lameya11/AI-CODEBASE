/**
 * Tests for the API client error handling.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getRepo, listRepos, deleteRepo } from '../src/api/client.js'

// Mock fetch globally
beforeEach(() => {
  global.fetch = vi.fn()
})

describe('API client error handling', () => {
  it('throws a structured error on 404', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 404,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Repository not found' }),
    })

    await expect(getRepo('nonexistent')).rejects.toThrow('Repository not found')
  })

  it('throws with status on error', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 422,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Validation error' }),
    })

    try {
      await listRepos()
    } catch (e) {
      expect(e.status).toBe(422)
      expect(e.message).toBe('Validation error')
    }
  })

  it('resolves successfully on 2xx', async () => {
    const mockData = [{ id: '1', name: 'test', status: 'ready' }]
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => mockData,
    })

    const result = await listRepos()
    expect(result).toEqual(mockData)
  })

  it('handles non-JSON error responses', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 500,
      headers: { get: () => 'text/html' },
      json: async () => { throw new Error('not json') },
    })

    await expect(getRepo('x')).rejects.toThrow('HTTP 500')
  })

  it('sends correct URL for getRepo', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ id: 'abc', name: 'test', status: 'ready' }),
    })

    await getRepo('abc')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/repos/abc',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) })
    )
  })

  it('sends DELETE for deleteRepo', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 204,
      headers: { get: () => '' },
      text: async () => '',
    })

    await deleteRepo('abc')
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/repos/abc',
      expect.objectContaining({ method: 'DELETE' })
    )
  })
})
