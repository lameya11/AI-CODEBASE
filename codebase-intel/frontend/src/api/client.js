/**
 * API client: typed fetch wrappers for every backend endpoint.
 * All functions throw a structured error on non-2xx responses.
 */

const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

// ---- Repositories ----

export const createRepoFromGitHub = (url, name) =>
  request('/repos', {
    method: 'POST',
    body: JSON.stringify({ source_type: 'github', url, name }),
  });

export const createRepoFromZip = (file, name) => {
  const form = new FormData();
  form.append('file', file);
  if (name) form.append('name', name);
  return fetch(`${BASE}/repos/upload`, { method: 'POST', body: form }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const err = new Error(body.detail || `HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  });
};

export const listRepos = () => request('/repos');
export const getRepo = (id) => request(`/repos/${id}`);
export const deleteRepo = (id) => request(`/repos/${id}`, { method: 'DELETE' });
export const reanalyzeRepo = (id) => request(`/repos/${id}/reanalyze`, { method: 'POST' });

// ---- Files ----

export const listFiles = (repoId) => request(`/repos/${repoId}/files`);
export const getFile = (repoId, fileId) => request(`/repos/${repoId}/files/${fileId}`);
export const getFileContent = (repoId, fileId) => request(`/repos/${repoId}/files/${fileId}/content`);

// ---- Graph ----

export const getGraph = (repoId, level = 'file') =>
  request(`/repos/${repoId}/graph?level=${level}`);

// ---- Search ----

export const searchRepo = (repoId, q, k = 8) =>
  request(`/repos/${repoId}/search?q=${encodeURIComponent(q)}&k=${k}`);

// ---- Chat ----

export const sendChatMessage = (repoId, question, history = []) =>
  request(`/repos/${repoId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ question, history }),
  });

export const getChatHistory = (repoId) => request(`/repos/${repoId}/chat`);

// ---- Impact ----

export const analyzeImpact = (repoId, filePath, maxDepth = 4) =>
  request(`/repos/${repoId}/impact`, {
    method: 'POST',
    body: JSON.stringify({ file_path: filePath, max_depth: maxDepth }),
  });

// ---- Issues ----

export const listIssues = (repoId, type, severity) => {
  const params = new URLSearchParams();
  if (type) params.append('type', type);
  if (severity) params.append('severity', severity);
  return request(`/repos/${repoId}/issues?${params}`);
};

// ---- Stats ----

export const getStats = (repoId) => request(`/repos/${repoId}/stats`);
