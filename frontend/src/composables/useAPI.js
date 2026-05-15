import axios from 'axios'

let _toast = null

export function setToastFn(fn) { _toast = fn }

const http = axios.create({ timeout: 15000 })

http.interceptors.response.use(
  r => r,
  err => {
    const msg = err.response?.data?.error || err.message || '请求失败'
    _toast?.(msg, 'error')
    return Promise.reject(err)
  }
)

async function sha256(message) {
  const buf = new TextEncoder().encode(message)
  const hash = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('')
}

async function getChallenge() {
  const { data } = await http.get('/api/auth/challenge')
  return data
}

async function getAuthCheck() {
  const { data } = await http.get('/api/auth/check')
  return data
}

async function getAuthHeaders() {
  const pwd = sessionStorage.getItem('bili-auth-password')
  if (!pwd) return {}
  const ch = await getChallenge()
  const resp = await sha256(`${ch.nonce}${ch.timestamp}${pwd}`)
  return {
    'X-Auth-Nonce': ch.nonce,
    'X-Auth-Timestamp': String(ch.timestamp),
    'X-Auth-Response': resp,
  }
}

async function verifyPassword(password) {
  const ch = await getChallenge()
  const resp = await sha256(`${ch.nonce}${ch.timestamp}${password}`)
  const { data } = await http.post('/api/auth/verify', {
    nonce: ch.nonce,
    timestamp: ch.timestamp,
    response: resp,
  })
  return data
}

const API = {
  async getConfig() {
    const { data } = await http.get('/api/config')
    return data
  },
  async saveConfig(interval) {
    const headers = await getAuthHeaders()
    const { data } = await http.post('/api/config', { interval }, { headers })
    return data
  },
  async getVideos() {
    const { data } = await http.get('/api/videos')
    return data
  },
  async addVideo(bvid) {
    const headers = await getAuthHeaders()
    const { data } = await http.post('/api/videos', { bvid }, { headers })
    return data
  },
  async deleteVideo(id) {
    const headers = await getAuthHeaders()
    await http.delete(`/api/videos/${id}`, { headers })
  },
  async toggleScore(id, enabled) {
    const headers = await getAuthHeaders()
    await http.patch(`/api/videos/${id}`, { score_enabled: enabled }, { headers })
  },
  async togglePaused(id, paused) {
    const headers = await getAuthHeaders()
    await http.patch(`/api/videos/${id}`, { paused }, { headers })
  },
  async getLatest(videoId) {
    const { data } = await http.get('/api/latest', { params: { video_id: videoId } })
    return data
  },
  async getSnapshots(videoId, hours) {
    const { data } = await http.get('/api/snapshots', { params: { video_id: videoId, hours } })
    return data
  },
  getAuthCheck,
  verifyPassword,
}

export function useAPI() {
  return API
}
