<script setup>
import { ref, watch, onMounted, onUnmounted, inject, nextTick, reactive, computed } from 'vue'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

const props = defineProps({
  selectedId: Number,
  snapshot: Object,
  currentHours: { type: Number, default: 24 },
  scoreEnabled: { type: Boolean, default: true },
  refreshKey: { type: Number, default: 0 },
})
const emit = defineEmits(['update:hours'])

const api = inject('api')

const METRICS = {
  view_count:   { label: '播放', color: '#1890ff' },
  danmaku:      { label: '弹幕', color: '#722ed1' },
  reply:        { label: '评论', color: '#13c2c2' },
  favorite:     { label: '收藏', color: '#fa8c16' },
  coin:         { label: '硬币', color: '#eb2f96' },
  like_count:   { label: '点赞', color: '#fa541c' },
  online_total: { label: '正在观看', color: '#52c41a' },
  score_total:  { label: '得点', color: '#4f8ef7' },
}

// Filtered entries for template v-for (excludes score_total when disabled)
const visibleMetrics = computed(() => {
  const entries = Object.entries(METRICS)
  if (props.scoreEnabled) return entries
  return entries.filter(([k]) => k !== 'score_total')
})

const DEFAULTS = {
  view_count: true, danmaku: false, reply: false, favorite: false,
  coin: false, like_count: false, online_total: false, score_total: true,
}

const STORAGE_KEY = 'bili-chart-toggles'

function loadToggles() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch (e) { /* ignore */ }
  return { ...DEFAULTS }
}

function saveToggles(v) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(v)) } catch (e) { /* ignore */ }
}

const toggles = reactive(loadToggles())
const hoursOptions = [1, 6, 24, 72, 168]
const currentH = ref(24)
const charts = {}
const containerRef = ref(null)
let historyData = []
const loading = ref(true)

const ttVisible = ref(false)
const ttTime = ref('')
const ttItems = ref([])
const ttX = ref(0)
const ttY = ref(0)

watch(toggles, saveToggles, { deep: true })

function setHours(h) {
  currentH.value = h
  emit('update:hours', h)
  loadHistory()
}

function formatTs(ts) {
  if (!ts) return '-'
  const t = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(t.getMonth()+1)}-${pad(t.getDate())} ${pad(t.getHours())}:${pad(t.getMinutes())}`
}

function smoothSeries(data, key, window = 3) {
  const half = Math.floor(window / 2)
  return data.map((r, i) => {
    let sum = 0, count = 0
    for (let j = Math.max(0, i - half); j < Math.min(data.length, i + half + 1); j++) {
      const v = Number(data[j][key])
      if (!isNaN(v)) { sum += v; count++ }
    }
    return count > 0 ? sum / count : null
  })
}

// Downsample using Largest Triangle Three Buckets to preserve visual shape
function lttb(data, targetCount) {
  const dataLen = data.length
  if (dataLen <= targetCount || targetCount < 3) return data

  const result = new Array(targetCount)
  result[0] = data[0]
  result[targetCount - 1] = data[dataLen - 1]

  const bucketSize = (dataLen - 2) / (targetCount - 2)
  let a = 0 // index of last selected point

  for (let i = 0; i < targetCount - 2; i++) {
    const bucketStart = Math.floor((i + 1) * bucketSize) + 1
    const bucketEnd = Math.floor((i + 2) * bucketSize) + 1
    const nextBucketPt = data[Math.min(bucketEnd, dataLen - 1)]

    let maxArea = -1, maxIdx = bucketStart
    const pa = data[a]

    for (let j = bucketStart; j < bucketEnd && j < dataLen - 1; j++) {
      const pb = data[j]
      const area = Math.abs(
        (pa[0] - nextBucketPt[0]) * (pb[1] - pa[1]) -
        (pa[0] - pb[0]) * (nextBucketPt[1] - pa[1])
      )
      if (area > maxArea) { maxArea = area; maxIdx = j }
    }
    result[i + 1] = data[maxIdx]
    a = maxIdx
  }
  return result
}

function buildData(data, key) {
  const raw = []
  const smoothedVals = smoothSeries(data, key, 17)
  for (let i = 0; i < data.length; i++) {
    raw.push([
      new Date(data[i].timestamp).getTime() / 1000,
      smoothedVals[i],
    ])
  }
  // Downsample for visual smoothness — desktop with many points looks jagged
  const bucket = lttb(raw, 200)
  const timestamps = bucket.map(p => p[0])
  const values = bucket.map(p => p[1])
  return [timestamps, values]
}

function valFormatter(v) {
  if (v == null) return '-'
  return v >= 1000000 ? (v/1000000).toFixed(1)+'M' : v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(0)
}

// Shared tooltip update — called from setCursor hook on the first chart
function updateTooltip(u) {
  if (u.cursor.left == null || u.cursor.left < 0) {
    ttVisible.value = false
    return
  }
  const ts = u.posToVal(u.cursor.left, 'x') * 1000
  let closest = null, minDiff = Infinity
  for (let i = 0; i < historyData.length; i++) {
    const diff = Math.abs(new Date(historyData[i].timestamp).getTime() - ts)
    if (diff < minDiff) { minDiff = diff; closest = historyData[i] }
  }
  if (!closest || minDiff > 120000) { ttVisible.value = false; return }

  ttTime.value = formatTs(closest.timestamp)
  const se = props.scoreEnabled
  ttItems.value = Object.entries(METRICS)
    .filter(([k]) => toggles[k] && (k !== 'score_total' || se))
    .map(([k, m]) => ({
      color: m.color,
      label: m.label,
      value: closest[k] != null ? Number(closest[k]).toLocaleString() : '-',
    }))

  const rect = u.root.getBoundingClientRect()
  const tipW = 220
  const M = 14
  let tx = rect.left + u.cursor.left + M
  if (tx + tipW > window.innerWidth - 4) tx = rect.left + u.cursor.left - tipW - M
  if (tx < 4) tx = 4
  ttX.value = tx
  ttY.value = rect.top - 10
  ttVisible.value = true
}

function hideTooltip() {
  ttVisible.value = false
}

function makeOpts(m) {
  const fmtVal = (self, val) => val == null ? '-' : valFormatter(val)

  return {
    width: 0,
    height: 100,
    cursor: {
      show: { x: true, y: false },
      drag: { x: true, y: false, setScale: false },
      sync: { key: 'bili-charts' },
      points: { show: false },
      focus: { prox: 50 },
    },
    select: { show: false, left: 0, width: 0, top: 0, height: 0 },
    legend: { show: false },
    series: [
      {},
      {
        stroke: m.color,
        width: 1.5,
        fill: (u, seriesIdx) => {
          const h = u.bbox.height * (window.devicePixelRatio || 1)
          const grad = u.ctx.createLinearGradient(0, 0, 0, h)
          grad.addColorStop(0, m.color + '30')
          grad.addColorStop(1, m.color + '02')
          return grad
        },
        spanGaps: true,
        points: { show: false },
        value: (self, v) => fmtVal(self, v),
      },
    ],
    axes: [
      {
        show: false,
        font: '10px sans-serif',
        grid: { show: false },
        ticks: { show: false },
      },
      {
        show: true,
        font: '9px sans-serif',
        stroke: '#999',
        grid: { stroke: '#f0f0f0', width: 1 },
        size: 50,
        values: (self, ticks) => ticks.map(v => valFormatter(v)),
      },
    ],
    hooks: {
      ready: [
        (u) => {
          u.over.addEventListener('mouseleave', () => {
            if (!('ontouchstart' in window)) hideTooltip()
          })
          // Auto-resize when container size changes (flex layout, sidebar toggle, etc.)
          if (window.ResizeObserver) {
            const ro = new ResizeObserver(() => {
              u.setSize({ width: u.root.clientWidth || 400, height: 100 })
            })
            ro.observe(u.root)
          }
        },
      ],
      setCursor: [(u) => updateTooltip(u)],
    },
  }
}

async function loadHistory() {
  if (!props.selectedId) { loading.value = false; return }
  loading.value = true
  destroyAll()
  historyData = []
  try {
    const data = await api.getSnapshots(props.selectedId, currentH.value)
    historyData = data
    renderAll()
  } finally {
    loading.value = false
  }
}

function destroyAll() {
  Object.values(charts).forEach(c => {
    try { c.destroy() } catch (e) { /* ignore */ }
  })
  Object.keys(charts).forEach(k => delete charts[k])
}

function renderAll() {
  nextTick(() => {
    requestAnimationFrame(() => {
      const se = props.scoreEnabled
      const visibleKeys = Object.keys(METRICS).filter(k => toggles[k] && (k !== 'score_total' || se))
      visibleKeys.forEach((k, idx) => {
        const el = containerRef.value?.querySelector(`[data-chart="${k}"]`)
        if (!el) return
        if (charts[k]) {
          try { charts[k].destroy() } catch (e) { /* ignore */ }
        }
        const data = buildData(historyData, k)
        const opts = makeOpts(METRICS[k])
        charts[k] = new uPlot(opts, data, el)
        try { charts[k].setSize({ width: el.clientWidth || 400, height: 100 }) } catch (e) { /* ignore */ }
      })
    })
  })
}

watch(() => props.snapshot, s => {
  if (!s || s.video_id !== props.selectedId) return
  historyData.push({
    timestamp: s.timestamp,
    view_count: s.view_count, danmaku: s.danmaku, reply: s.reply,
    favorite: s.favorite, coin: s.coin, share: s.share, like_count: s.like_count,
    online_total: s.online_total, online_count: s.online_count,
    score_play: s.score_play, score_interact: s.score_interact, score_fav: s.score_fav,
    score_coin: s.score_coin, score_like: s.score_like, score_total: s.score_total,
  })
  if (historyData.length > 2000) historyData = historyData.slice(-2000)
  const se = props.scoreEnabled
  Object.entries(METRICS).forEach(([k]) => {
    if (!toggles[k] || !charts[k]) return
    if (k === 'score_total' && !se) return
    charts[k].setData(buildData(historyData, k))
  })
})

watch(() => props.selectedId, () => {
  destroyAll()
  loadHistory()
})

watch(toggles, () => {
  if (historyData.length) renderAll()
})

watch(() => props.scoreEnabled, () => {
  if (historyData.length) renderAll()
})

watch(() => props.refreshKey, () => {
  if (props.selectedId) loadHistory()
})

function onResize() {
  requestAnimationFrame(() => {
    Object.values(charts).forEach(c => {
      try {
        const el = c.root
        c.setSize({ width: el.clientWidth || 400, height: 100 })
      } catch (e) { /* ignore */ }
    })
  })
}

function onDocumentTouch(e) {
  const inside = Object.values(charts).some(c => {
    try {
      const r = c.root.getBoundingClientRect()
      const cx = e.clientX ?? (e.touches?.[0]?.clientX ?? 0)
      const cy = e.clientY ?? (e.touches?.[0]?.clientY ?? 0)
      return cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom
    } catch (_) { return false }
  })
  if (!inside) hideTooltip()
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  window.addEventListener('touchstart', onDocumentTouch, { passive: true })
  nextTick(loadHistory)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('touchstart', onDocumentTouch)
  destroyAll()
})
</script>

<template>
  <div class="chart-panel">
    <div class="toolbar">
      <span class="tool-label">范围</span>
      <button v-for="h in hoursOptions" :key="h"
        :class="['range-btn', { active: currentH === h }]" @click="setHours(h)"
      >{{ h === 1 ? '1h' : h === 6 ? '6h' : h === 24 ? '24h' : h === 72 ? '3d' : '7d' }}</button>
      <span class="sep"></span>
      <span class="tool-group">
        <span class="tool-label">显示</span>
        <label v-for="[k, m] in visibleMetrics" :key="k" class="metric-toggle">
          <input type="checkbox" v-model="toggles[k]" />
          <span class="check-box"></span>
          <span class="dot" :style="{ background: m.color }"></span>
          {{ m.label }}
        </label>
      </span>
    </div>
    <div class="charts-scroll" ref="containerRef">
      <div v-if="loading" class="overlay-spinner"><span class="spinner"></span></div>
      <template v-for="[k, m] in visibleMetrics" :key="k">
        <div v-show="toggles[k]" class="chart-row">
          <div class="row-label">
            <span class="row-dot" :style="{ background: m.color }"></span>
            {{ m.label }}
          </div>
          <div :data-chart="k" class="mini-chart"></div>
        </div>
      </template>
      <div v-if="!loading && !selectedId" class="empty">请选择一个视频开始监控</div>
      <div v-else-if="!loading && historyData.length === 0" class="empty">暂无历史数据</div>
    </div>
    <Teleport to="body">
      <Transition name="tt-fade">
        <div v-if="ttVisible" class="custom-tooltip" :style="{ left: ttX + 'px', top: ttY + 'px' }">
          <div class="tt-time">{{ ttTime }}</div>
          <div v-for="item in ttItems" :key="item.label" class="tt-row">
            <span class="tt-dot" :style="{ background: item.color }"></span>
            <span class="tt-label">{{ item.label }}</span>
            <span class="tt-value">{{ item.value }}</span>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.chart-panel {
  background: #fff; border-radius: 10px; padding: 14px 18px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04); display: flex; flex-direction: column;
  -webkit-tap-highlight-color: transparent;
}
.toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.tool-label { font-size: 12px; font-weight: 600; color: #555; }
.range-btn {
  border: 1px solid #e0e0e0; background: #fff; border-radius: 5px; padding: 4px 13px;
  font-size: 12px; cursor: pointer; font-weight: 500; color: #666; transition: all .15s;
  -webkit-tap-highlight-color: transparent; outline: none;
}
.range-btn:hover { border-color: #4f8ef7; color: #4f8ef7; }
.range-btn.active { background: #4f8ef7; color: #fff; border-color: #4f8ef7; }
.range-btn:focus { outline: none; }
.sep { width: 1px; height: 15px; background: #e8e8e8; margin: 0 5px; }
.tool-group { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.metric-toggle {
  font-size: 12px; display: flex; align-items: center; gap: 4px;
  cursor: pointer; user-select: none; color: #666;
  -webkit-tap-highlight-color: transparent; outline: none;
}
.metric-toggle input { position: absolute; opacity: 0; width: 0; height: 0; }
.check-box {
  width: 14px; height: 14px; border: 1.5px solid #d0d0d0; border-radius: 3px;
  transition: all .15s; flex-shrink: 0; position: relative;
}
.metric-toggle input:checked + .check-box { background: #4f8ef7; border-color: #4f8ef7; }
.metric-toggle input:checked + .check-box::after {
  content: ''; position: absolute; left: 3px; top: 1px; width: 5px; height: 8px;
  border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg);
}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-left: 2px; }
.charts-scroll { flex: 1; overflow-y: auto; overflow-x: hidden; min-height: 0; position: relative; -webkit-tap-highlight-color: transparent; }
.chart-row { display: flex; align-items: stretch; margin-bottom: 2px; -webkit-tap-highlight-color: transparent; }
.row-label {
  width: 64px; flex-shrink: 0; display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: #666; padding: 4px 0; white-space: nowrap;
}
.row-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.mini-chart { flex: 1; height: 100px; -webkit-tap-highlight-color: transparent; }

.overlay-spinner {
  position: absolute; inset: 0; z-index: 10;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.7);
  backdrop-filter: blur(1px);
}
.spinner {
  width: 28px; height: 28px; border: 3px solid #e0e0e0;
  border-top-color: #4f8ef7; border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty { text-align: center; padding: 40px 0; color: #aaa; font-size: 13px; }

.custom-tooltip {
  position: fixed; z-index: 9999;
  background: #fff; border-radius: 8px; padding: 10px 14px;
  box-shadow: 0 4px 24px rgba(0,0,0,.12); border: 1px solid #e8e8e8;
  min-width: 160px; max-width: 220px; pointer-events: none; user-select: none;
  white-space: nowrap;
}
.tt-time { font-size: 12px; font-weight: 600; color: #333; margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid #f0f0f0; }
.tt-row { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; font-size: 12px; }
.tt-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.tt-label { color: #888; min-width: 52px; }
.tt-value { color: #333; font-weight: 500; }
.tt-fade-enter-active { transition: opacity .12s; }
.tt-fade-leave-active { transition: opacity .1s; }
.tt-fade-enter-from, .tt-fade-leave-to { opacity: 0; }

@media (max-width: 640px) {
  .charts-scroll { overflow-y: visible; }
  .mini-chart { height: 70px; }
  .row-label { width: 42px; font-size: 10px; }
  .toolbar { gap: 4px; }
  .tool-group { gap: 4px; }
  .custom-tooltip { right: 4px; padding: 8px 10px; min-width: 140px; font-size: 11px; }
}
</style>

<style>
.u-cursor-y { display: none !important; }
.uplot canvas, .u-over, .u-under { -webkit-tap-highlight-color: transparent; }
</style>
