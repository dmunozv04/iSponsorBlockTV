export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers)
  if (options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin', cache: 'no-store' })
  if (response.status === 401 && !['/api/auth/login', '/api/auth/session'].includes(path)) {
    window.dispatchEvent(new Event('session-expired'))
  }
  return response
}

export async function apiJson(path, options) {
  const response = await apiFetch(path, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Please try again.')
  }
  return data
}
