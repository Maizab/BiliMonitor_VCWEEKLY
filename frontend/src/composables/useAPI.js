import axios from 'axios'
import SHA256 from 'crypto-js/sha256'

let _toast = null

export function setToastFn(fn) { _toast = fn }

const apiBase = import.meta.env.VITE_API_BASE || '/api'
const http = axios.create({ timeout: 15000, baseURL: apiBase })

http.interceptors.response.use(
  r => r,
  err => {
    const msg = err.response?.data?.error || err.message || '请求失败'
    _toast?.(msg, 'error')
    return Promise.reject(err)
  }
)

function sha256(message) {
  return SHA256(message).toString()
}

async function getChallenge() {
  const { data } = await http.get('/auth/challenge')
  return data
}

async function getAuthCheck() {
  const { data } = await http.get('/auth/check')
  return data
}

async function getAuthHeaders() {
  const pwd = sessionStorage.getItem('auth-password')
  if (!pwd) return {}
  const ch = await getChallenge()
  const resp = sha256(`${ch.nonce}${ch.timestamp}${pwd}`)
  return {
    'X-Auth-Nonce': ch.nonce,
    'X-Auth-Timestamp': String(ch.timestamp),
    'X-Auth-Response': resp,
  }
}

async function verifyPassword(password) {
  const ch = await getChallenge()
  const resp = sha256(`${ch.nonce}${ch.timestamp}${password}`)
  const { data } = await http.post('/auth/verify', {
    nonce: ch.nonce,
    timestamp: ch.timestamp,
    response: resp,
  })
  return data
}

const API = {
  async getConfig() {
    const { data } = await http.get('/config')
    return data
  },
  async saveConfig(interval) {
    const headers = await getAuthHeaders()
    const { data } = await http.post('/config', { interval }, { headers })
    return data
  },
  async getVideos() {
    const { data } = await http.get('/videos')
    return data
  },
  async addVideo(bvid) {
    const headers = await getAuthHeaders()
    const { data } = await http.post('/videos', { bvid }, { headers })
    return data
  },
  async deleteVideo(id) {
    const headers = await getAuthHeaders()
    await http.delete(`/videos/${id}`, { headers })
  },
  async toggleScore(id, enabled) {
    const headers = await getAuthHeaders()
    await http.patch(`/videos/${id}`, { score_enabled: enabled }, { headers })
  },
  async togglePaused(id, paused) {
    const headers = await getAuthHeaders()
    await http.patch(`/videos/${id}`, { paused }, { headers })
  },
  async getLatest(videoId) {
    const { data } = await http.get('/latest', { params: { video_id: videoId } })
    return data
  },
  async getSnapshots(videoId, hours) {
    const { data } = await http.get('/snapshots', { params: { video_id: videoId, hours } })
    return data
  },
  getAuthCheck,
  verifyPassword,
}

export function useAPI() {
  return API
}
