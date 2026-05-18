<script setup>
import { ref, provide, onMounted, onUnmounted, watch, computed } from 'vue'
import { useAPI, setToastFn } from './composables/useAPI.js'
import { useSSE } from './composables/useSSE.js'
import { useNumberFormat } from './composables/useNumberFormat.js'
import StatusBar from './components/StatusBar.vue'
import SettingsModal from './components/SettingsModal.vue'
import ManagementModal from './components/ManagementModal.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import Toast from './components/Toast.vue'
import VideoManager from './components/VideoManager.vue'
import DataCards from './components/DataCards.vue'
import ChartPanel from './components/ChartPanel.vue'
import ExportModal from './components/ExportModal.vue'


const api = useAPI()
const { status, logLines, snapshot, videos: sseVideos, connect, disconnect } = useSSE()
const { fmt: fmtNum, mode: fmtMode } = useNumberFormat()

const videos = ref([])
const selectedId = ref(null)
const showSettings = ref(false)
const showManagement = ref(false)
const showExport = ref(false)
const exportVideoId = ref(null)
const exportVideoTitle = ref('')
const latestSnapshot = ref(null)
const referenceSnapshot = ref(null)
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
provide('referenceSnapshot', referenceSnapshot)
provide('currentHours', currentHours)
provide('confirm', confirmRef)
provide('toast', toastRef)
provide('pageReady', pageReady)
provide('logLines', logLines)
provide('fmtNum', fmtNum)
provide('fmtMode', fmtMode)

setToastFn((msg, type) => toastRef.value?.show(msg, type))

watch(snapshot, async s => {
  if (s && s.video_id === selectedId.value) {
    latestSnapshot.value = s
    // 增量参考点只在切换视频或手动刷新时更新，SSE 推送不频繁更新
  }
})

async function fetchLatestAndRef(id) {
  dataLoading.value = true
  try {
    const [latest, ref] = await Promise.all([
      api.getLatest(id),
      api.getReference(id).catch(() => null),
    ])
    latestSnapshot.value = latest
    referenceSnapshot.value = ref
  } catch (e) {}
  dataLoading.value = false
}

watch(selectedId, async (id) => {
  if (!id) { latestSnapshot.value = null; referenceSnapshot.value = null; return }
  await fetchLatestAndRef(id)
}, { immediate: false })

watch(sseVideos, (list) => {
  videos.value = list
  if (selectedId.value && !list.find(v => v.id === selectedId.value)) {
    selectedId.value = list.length ? list[0].id : null
  }
})

async function fetchInitial() {
  await loadVideos()
  if (selectedId.value) {
    try {
      const [latest, ref] = await Promise.all([
        api.getLatest(selectedId.value),
        api.getReference(selectedId.value).catch(() => null),
      ])
      latestSnapshot.value = latest
      referenceSnapshot.value = ref
    } catch (e) {}
  }
  setTimeout(() => { pageReady.value = true }, 300)
}

async function loadVideos() {
  try {
    videos.value = await api.getVideos()
  } catch (e) { return }
  const lastId = localStorage.getItem('selected-video')
  if (!selectedId.value && videos.value.length) {
    const restored = lastId ? videos.value.find(v => v.id === Number(lastId)) : null
    selectedId.value = restored ? restored.id : videos.value[0].id
  }
  if (selectedId.value && !videos.value.find(v => v.id === selectedId.value)) {
    selectedId.value = videos.value.length ? videos.value[0].id : null
  }
}

const selectedVideo = computed(() => videos.value.find(v => v.id === selectedId.value))
const scoreEnabled = computed(() => selectedVideo.value ? !!selectedVideo.value.score_enabled : true)

function onSelectVideo(id) {
  selectedId.value = id
  localStorage.setItem('selected-video', id)
}
async function onSettingsChange() {
  await loadVideos()
  refreshKey.value++
  if (selectedId.value) {
    await fetchLatestAndRef(selectedId.value)
  }
}

onMounted(() => {
  connect()
  fetchInitial()
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
    @open-settings="showSettings = true"
    @open-management="showManagement = true"
  />
  <SettingsModal v-if="pageReady" :show="showSettings" @close="showSettings = false" />
  <ManagementModal v-if="pageReady" :show="showManagement" @close="showManagement = false" @change="onSettingsChange" />
  <ExportModal v-if="pageReady" :show="showExport" :video-id="exportVideoId" :video-title="exportVideoTitle" @close="showExport = false" />
  <main v-if="pageReady" class="app-main">
    <div class="columns">
      <aside class="sidebar">
        <VideoManager
          :videos="videos"
          :selected-id="selectedId"
          @select="onSelectVideo"
          @export="v => { exportVideoId = v.id; exportVideoTitle = v.title || v.bvid; showExport = true }"
        />
        <DataCards :snapshot="latestSnapshot" :reference="referenceSnapshot" :loading="dataLoading" :score-enabled="scoreEnabled" />
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
  </main>
</template>

<style>
*, *::before, *::after { -webkit-tap-highlight-color: transparent; }
.page-loading {
  display: flex; align-items: center; justify-content: center; height: 100vh;
}
.page-loading .spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
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
  .content { flex: none; }
  .app-main { padding: 10px 12px; }
}
</style>
