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

const API = {
  async getConfig() {
    const { data } = await http.get('/api/config')
    return data
  },
  async saveConfig(interval, cookie) {
    const { data } = await http.post('/api/config', { interval, cookie })
    return data
  },
  async getVideos() {
    const { data } = await http.get('/api/videos')
    return data
  },
  async addVideo(bvid) {
    const { data } = await http.post('/api/videos', { bvid })
    return data
  },
  async deleteVideo(id) {
    await http.delete(`/api/videos/${id}`)
  },
  async toggleScore(id, enabled) {
    await http.patch(`/api/videos/${id}`, { score_enabled: enabled })
  },
  async getLatest(videoId) {
    const { data } = await http.get('/api/latest', { params: { video_id: videoId } })
    return data
  },
  async getSnapshots(videoId, hours) {
    const { data } = await http.get('/api/snapshots', { params: { video_id: videoId, hours } })
    return data
  },
}

export function useAPI() {
  return API
}
