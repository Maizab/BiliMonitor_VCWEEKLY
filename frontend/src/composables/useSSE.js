
import { ref } from 'vue'

const apiBase = import.meta.env.VITE_API_BASE || '/api'

export function useSSE() {
  const status = ref({ running: false, last_fetch: null, last_error: null })
  const logLines = ref([])
  const snapshot = ref(null)
  const videos = ref([])
  let es = null

  function connect() {
    es = new EventSource(`${apiBase}/stream`)

    es.addEventListener('status', e => {
      status.value = JSON.parse(e.data)
    })

    es.addEventListener('log', e => {
      const d = JSON.parse(e.data)
      logLines.value.push(...(d.lines || []))
      if (logLines.value.length > 200) {
        logLines.value = logLines.value.slice(-200)
      }
    })

    es.addEventListener('snapshot', e => {
      snapshot.value = JSON.parse(e.data)
    })

    es.addEventListener('videos', e => {
      videos.value = JSON.parse(e.data)
    })

    es.onmessage = e => {
      const d = JSON.parse(e.data)
      if (d.status) status.value = d.status
      if (d.log) logLines.value = d.log
      if (d.videos) videos.value = d.videos
    }

    es.onerror = () => {}
  }

  function disconnect() {
    if (es) { es.close(); es = null }
  }

  return { status, logLines, snapshot, videos, connect, disconnect }
}
