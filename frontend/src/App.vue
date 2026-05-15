<script setup>
import { ref, provide, onMounted, onUnmounted, watch, computed } from 'vue'
import { useAPI, setToastFn } from './composables/useAPI.js'
import { useSSE } from './composables/useSSE.js'
import StatusBar from './components/StatusBar.vue'
import SettingsModal from './components/SettingsModal.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import Toast from './components/Toast.vue'
import VideoManager from './components/VideoManager.vue'
import DataCards from './components/DataCards.vue'
import ChartPanel from './components/ChartPanel.vue'
import LogBar from './components/LogBar.vue'

const api = useAPI()
const { status, logLines, snapshot, connect, disconnect } = useSSE()

const videos = ref([])
const selectedId = ref(null)
const showSettings = ref(false)
const showLog = ref(false)
const latestSnapshot = ref(null)
const dataLoading = ref(false)
const currentHours = ref(24)
const confirmRef = ref(null)
const toastRef = ref(null)
const pageReady = ref(false)
const refreshKey = ref(0)

provide('api', api)
provide('status', status)
provide('videos', videos)
provide('selectedId', selectedId)
provide('latestSnapshot', latestSnapshot)
provide('currentHours', currentHours)
provide('confirm', confirmRef)
provide('toast', toastRef)
provide('pageReady', pageReady)

setToastFn((msg, type) => toastRef.value?.show(msg, type))

watch(snapshot, s => {
  if (s && s.video_id === selectedId.value) {
    latestSnapshot.value = s
  }
})

watch(selectedId, async (id) => {
  if (!id) { latestSnapshot.value = null; return }
  dataLoading.value = true
  try { latestSnapshot.value = await api.getLatest(id) } catch (e) {}
  dataLoading.value = false
}, { immediate: false })

async function fetchInitial() {
  await loadVideos()
  if (selectedId.value) {
    try { latestSnapshot.value = await api.getLatest(selectedId.value) } catch (e) {}
  }
  // Brief delay to let ChartPanel finish its initial render
  setTimeout(() => { pageReady.value = true }, 300)
}

async function loadVideos() {
  try {
    videos.value = await api.getVideos()
  } catch (e) { return }
  const lastId = localStorage.getItem('bili-selected-video')
  if (!selectedId.value && videos.value.length) {
    const restored = lastId ? videos.value.find(v => v.id === Number(lastId)) : null
    selectedId.value = restored ? restored.id : videos.value[0].id
  }
  if (selectedId.value && !videos.value.find(v => v.id === selectedId.value)) {
    selectedId.value = videos.value.length ? videos.value[0].id : null
  }
}

const scoreEnabled = computed(() => {
  const v = videos.value.find(v => v.id === selectedId.value)
  return v ? !!v.score_enabled : true
})

function onSelectVideo(id) {
  selectedId.value = id
  localStorage.setItem('bili-selected-video', id)
}
async function onSettingsChange() {
  await loadVideos()
  refreshKey.value++
  if (selectedId.value) {
    dataLoading.value = true
    try { latestSnapshot.value = await api.getLatest(selectedId.value) } catch (e) {}
    dataLoading.value = false
  }
}

onMounted(() => {
  connect()
  fetchInitial()
  setInterval(loadVideos, 10000)
})

onUnmounted(() => disconnect())
</script>

<template>
  <ConfirmDialog ref="confirmRef" />
  <Toast ref="toastRef" />
  <div v-if="!pageReady" class="page-loading">
    <span class="spinner"></span>
  </div>
  <StatusBar
    v-if="pageReady"
    :status="status"
    :show-log="showLog"
    @toggle-log="showLog = !showLog"
    @open-settings="showSettings = true"
  />
  <SettingsModal v-if="pageReady" :show="showSettings" @close="showSettings = false" @change="onSettingsChange" />
  <main v-if="pageReady" class="app-main">
    <div class="columns">
      <aside class="sidebar">
        <VideoManager
          :videos="videos"
          :selected-id="selectedId"
          @select="onSelectVideo"
        />
        <DataCards :snapshot="latestSnapshot" :loading="dataLoading" :score-enabled="scoreEnabled" />
      </aside>
      <section class="content">
        <ChartPanel
          :selected-id="selectedId"
          :snapshot="snapshot"
          :current-hours="currentHours"
          :score-enabled="scoreEnabled"
          :refresh-key="refreshKey"
          @update:hours="currentHours = $event"
        />
      </section>
    </div>
    <LogBar :lines="logLines" :show="showLog" />
  </main>
</template>

<style>
*, *::before, *::after { -webkit-tap-highlight-color: transparent; }
.page-loading {
  display: flex; align-items: center; justify-content: center; height: 100vh;
}
.page-loading .spinner {
  width: 32px; height: 32px; border: 3px solid #e0e0e0;
  border-top-color: #4f8ef7; border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.app-main {
  max-width: 1480px;
  margin: 0 auto;
  padding: 16px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.columns {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.sidebar {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.content {
  flex: 1;
  min-width: 0;
}
@media (max-width: 1100px) {
  .columns { flex-direction: column; }
  .sidebar { width: 100%; }
  .app-main { padding: 10px 12px; }
}
</style>
