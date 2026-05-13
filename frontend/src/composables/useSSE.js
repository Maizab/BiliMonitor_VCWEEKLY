
import { ref, onMounted, onUnmounted } from 'vue'

export function useSSE() {
  const status = ref({ running: false, last_fetch: null, last_error: null })
  const logLines = ref([])
  const snapshot = ref(null)
  let es = null

  function connect() {
    es = new EventSource('/api/stream')

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

    es.onmessage = e => {
      const d = JSON.parse(e.data)
      if (d.status) status.value = d.status
      if (d.log) logLines.value = d.log
    }

    es.onerror = () => {}
  }

  function disconnect() {
    if (es) { es.close(); es = null }
  }

  return { status, logLines, snapshot, connect, disconnect }
}
