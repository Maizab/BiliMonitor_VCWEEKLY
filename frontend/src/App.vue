<script setup>
import { ref, provide, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAPI, setToastFn } from './composables/useAPI.js'
import { useSSE } from './composables/useSSE.js'
import { useNumberFormat } from './composables/useNumberFormat.js'
import StatusBar from './components/StatusBar.vue'
import SettingsModal from './components/SettingsModal.vue'
import ManagementModal from './components/ManagementModal.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import Toast from './components/Toast.vue'
import UploaderBrowser from './components/UploaderBrowser.vue'
import DataCards from './components/DataCards.vue'
import ChartPanel from './components/ChartPanel.vue'
import ExportModal from './components/ExportModal.vue'


const router = useRouter()
const route = useRoute()

const api = useAPI()
const { status, logLines, snapshot, videos: sseVideos, connect, disconnect } = useSSE()
const { fmt: fmtNum, mode: fmtMode } = useNumberFormat()

const videos = ref([])
const uploaders = ref([])
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

// 当前 URL 中的 bvid（用于 UploaderBrowser 高亮）
const currentBvid = ref(null)

provide('api', api)
provide('status', status)
provide('videos', videos)
provide('uploaders', uploaders)
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

watch(sseVideos, async (list) => {
  videos.value = list
  // 刷新上传者分组
  try {
    uploaders.value = await api.getUploaders()
  } catch (e) { /* ignore */ }
  // 同步选中状态：如果当前视频被删除，清除选择
  if (currentBvid.value && !list.find(v => v.bvid === currentBvid.value)) {
    currentBvid.value = null
    selectedId.value = null
    router.replace('/')
  }
})

async function fetchInitial() {
  await loadVideos()
  await loadUploaders()
  // 根据 URL 路由恢复状态
  restoreFromRoute()
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
}

async function loadUploaders() {
  try {
    uploaders.value = await api.getUploaders()
  } catch (e) { /* ignore */ }
}

function restoreFromRoute() {
  // 从当前 URL hash 恢复浏览状态
  const hash = route.path
  const match = hash.match(/^\/(\d+)(?:\/(BV[1-9A-HJ-NP-Za-km-z]{10}))?$/)
  if (match) {
    const mid = Number(match[1])
    const bvid = match[2] || null
    // 在该上传者的视频中查找
    const uploader = uploaders.value.find(u => u.mid === mid)
    if (uploader && bvid) {
      const video = uploader.videos.find(v => v.bvid === bvid)
      if (video) {
        selectedId.value = video.id
        currentBvid.value = bvid
      }
    }
    // 如果路由是 /mid 但没有 bvid，不选中任何视频（显示空状态）
  } else if (hash === '/') {
    // 首页：检查 localStorage 中是否有上次路由
    const lastRoute = localStorage.getItem('last-route')
    if (lastRoute && lastRoute !== '/') {
      router.replace(lastRoute)
      return
    }
  }
}

// 监听路由变化（用户点击视频时通过 router.push 触发）
watch(() => route.fullPath, (path) => {
  if (path && path !== '/') {
    localStorage.setItem('last-route', path)
  }
  restoreFromRoute()
})

const selectedVideo = computed(() => videos.value.find(v => v.id === selectedId.value))
const scoreEnabled = computed(() => selectedVideo.value ? !!selectedVideo.value.score_enabled : true)

function onSelectVideo({ video, uploaderMid }) {
  if (!video || !uploaderMid) return
  selectedId.value = video.id
  currentBvid.value = video.bvid
  router.push(`/${uploaderMid}/${video.bvid}`)
}

function onVideoExport(v) {
  exportVideoId.value = v.id
  exportVideoTitle.value = v.title || v.bvid
  showExport.value = true
}

async function onSettingsChange() {
  await loadVideos()
  await loadUploaders()
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
        <UploaderBrowser
          :uploaders="uploaders"
          :selected-bvid="currentBvid"
          @select="onSelectVideo"
          @export="onVideoExport"
        />
        <DataCards :snapshot="latestSnapshot" :reference="referenceSnapshot" :loading="dataLoading" :score-enabled="scoreEnabled" />
      </aside>
      <section class="content">
        <div v-if="!selectedId" class="empty-state">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
          </div>
          <p>选择一个视频来查看</p>
        </div>
        <ChartPanel
          v-else
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
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; min-height: 300px; color: var(--text-placeholder);
}
.empty-icon { margin-bottom: 16px; opacity: .4; }
.empty-state p { font-size: 15px; margin: 0; }

@media (max-width: 1100px) {
  .columns { flex-direction: column; }
  .sidebar { width: 100%; }
  .content { flex: none; }
  .app-main { padding: 10px 12px; }
}
</style>
