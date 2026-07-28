const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

function getToken() {
  return localStorage.getItem('token')
}

async function request(path, { method = 'GET', body, auth = true, params } = {}) {
  const headers = { 'Content-Type': 'application/json' }

  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let url = `${API_URL}${path}`
  if (params) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString()
    if (query) url += `?${query}`
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.dispatchEvent(new Event('auth-expired'))
  }

  let data = null
  try {
    data = await res.json()
  } catch {
    // respuesta sin cuerpo JSON
  }

  if (!res.ok) {
    const detail = data?.detail || `Error ${res.status}`
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  return data
}

// ---------- Auth ----------
export const login = (username, password) =>
  request('/auth/login', { method: 'POST', body: { username, password }, auth: false })

export const register = (username, password) =>
  request('/auth/register', { method: 'POST', body: { username, password }, auth: false })

// ---------- Juegos ----------
export const getGames = (filters = {}) =>
  request('/games', { params: filters })

export const searchGamesByName = (q) =>
  request('/games/search', { params: { q } })

export const searchSemantic = (q) =>
  request('/games/similar', { params: { q } })

export const createGame = (game) =>
  request('/games', { method: 'POST', body: game })

export const addGameFromSteam = (app_id) =>
  request('/games/add', { method: 'POST', body: { app_id } })

export const updateGame = (appId, changes) =>
  request(`/games/${appId}`, { method: 'PUT', body: changes })

export const deleteGame = (appId) =>
  request(`/games/${appId}`, { method: 'DELETE' })

export const searchSteam = (q) =>
  request('/steam/search', { params: { q } })

export const getGameMedia = (appId) =>
  request(`/games/${appId}/media`)

export const retryVideo = (appId) =>
  request(`/games/${appId}/retry-video`, { method: 'POST' })

export const syncMediaTodos = (limite = 20) =>
  request('/media/sync-all', { method: 'POST', params: { limite } })

// ---------- Favoritos ----------
export const getFavorites = () => request('/favorites')

export const addFavorite = (app_id) =>
  request('/favorites', { method: 'POST', body: { app_id } })

export const removeFavorite = (appId) =>
  request(`/favorites/${appId}`, { method: 'DELETE' })

export const searchFavoritesSemantic = (q) =>
  request('/favorites/similar', { params: { q } })

// ---------- General ----------
export const checkHealth = () => request('/health', { auth: false })

export { API_URL }
