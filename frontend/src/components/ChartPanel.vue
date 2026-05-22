<script setup>
import { ref, watch, onMounted, onUnmounted, inject, nextTick, reactive, computed } from 'vue'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import DateTimePicker from './DateTimePicker.vue'

const props = defineProps({
  selectedId: Number,
  snapshot: Object,
  currentHours: { type: Number, default: 24 },
  scoreEnabled: { type: Boolean, default: true },
  refreshKey: { type: Number, default: 0 },
})
const emit = defineEmits(['update:hours'])

const api = inject('api')
const fmtNum = inject('fmtNum', n => n != null ? Number(n).toLocaleString() : '-')
const fmtMode = inject('fmtMode', null)

const METRICS = {
  view_count:   { label: '播放', color: '#1890ff' },
  danmaku:      { label: '弹幕', color: '#722ed1' },
  reply:        { label: '评论', color: '#13c2c2' },
  favorite:     { label: '收藏', color: '#fa8c16' },
  coin:         { label: '硬币', color: '#eb2f96' },
  like_count:   { label: '点赞', color: '#fa541c' },
  online_total: { label: '正在观看', color: '#52c41a' },
  score_total:  { label: '积累得点', color: '#4f8ef7' },
  incr_score_total: { label: '增量得点', color: '#14b8a6' },
}

// 增量得点是否有数据（非 computed，手动同步）
const hasIncr = ref(false)
function updateHasIncr() {
  hasIncr.value = historyData.length > 0 && historyData.some(d => d.incr_score_total != null)
}

// Filtered entries for template v-for（开关按钮始终可见）
const visibleMetrics = computed(() => {
  let entries = Object.entries(METRICS)
  if (!props.scoreEnabled) entries = entries.filter(([k]) => k !== 'score_total' && k !== 'incr_score_total')
  return entries
})

const DEFAULTS = {
  view_count: true, danmaku: false, reply: false, favorite: false,
  coin: false, like_count: false, online_total: false,
  score_total: true, incr_score_total: false,
}

const STORAGE_KEY = 'chart-toggles'

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
const charts = {}
const containerRef = ref(null)
let historyData = []
const hasData = ref(false)
const loading = ref(true)

const ttVisible = ref(false)
const ttTime = ref('')
const ttItems = ref([])
const ttX = ref(0)
const ttY = ref(0)

// 范围选择持久化
const RANGE_KEY = 'chart-range'

function loadRange() {
  try {
    const raw = localStorage.getItem(RANGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) { /* ignore */ }
  return { hours: 24, customMode: false, customStart: '', customEnd: '', customEndLive: true }
}

function saveRange() {
  try {
    localStorage.setItem(RANGE_KEY, JSON.stringify({
      hours: currentH.value,
      customMode: customMode.value,
      customStart: customStart.value,
      customEnd: customEnd.value,
      customEndLive: customEndLive.value,
    }))
  } catch (e) { /* ignore */ }
}

const saved = loadRange()
const currentH = ref(saved.hours || 24)
const customMode = ref(saved.customMode || false)
const customStart = ref(saved.customStart || new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString())
const customEnd = ref(saved.customEnd || new Date().toISOString())
const customEndLive = ref(saved.customEndLive !== false)

// 范围超出最早数据的提示
const rangeNotice = ref('')

function updateRangeNotice() {
  if (!historyData.length) {
    rangeNotice.value = ''
    return
  }
  const earliest = historyData[0]
  if (!earliest) {
    rangeNotice.value = ''
    return
  }
  let rangeStartMs
  if (customMode.value) {
    rangeStartMs = new Date(customStart.value).getTime()
  } else {
    rangeStartMs = Date.now() - currentH.value * 3600 * 1000
  }
  const firstMs = new Date(earliest.timestamp).getTime()
  // 给 2 分钟容差，避免范围起点与最早数据点过近时误报
  if (rangeStartMs + 120000 < firstMs) {
    rangeNotice.value = `范围已超出最早记录的数据，最早数据点为 ${formatTs(earliest.timestamp)}`
  } else {
    rangeNotice.value = ''
  }
}

watch(toggles, saveToggles, { deep: true })

function setHours(h) {
  customMode.value = false
  currentH.value = h
  emit('update:hours', h)
  saveRange()
  loadHistory()
}

function enterCustom() {
  customMode.value = true
  customStart.value = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString()
  customEnd.value = new Date().toISOString()
  customEndLive.value = true
  saveRange()
  loadHistory()
}

function onCustomParamChange() {
  if (!customEndLive.value && customStart.value && customEnd.value && customStart.value >= customEnd.value) {
    const s = new Date(customStart.value)
    const e = new Date(s.getTime() + 3600 * 1000)
    customEnd.value = e.toISOString()
  }
  saveRange()
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
    if (r[key] == null) return null  // 原值为 NULL 则保持 NULL，不平滑跨过
    let sum = 0, count = 0
    for (let j = Math.max(0, i - half); j < Math.min(data.length, i + half + 1); j++) {
      const v = Number(data[j][key])
      if (!isNaN(v) && data[j][key] != null) { sum += v; count++ }
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
      if (pb[1] == null || pa[1] == null || nextBucketPt[1] == null) continue
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
    const v = smoothedVals[i]
    raw.push([
      new Date(data[i].timestamp).getTime() / 1000,
      v == null ? null : v,
    ])
  }

  // Split into segments at gaps > 10 min, so downsampling doesn't bridge real data gaps
  const segments = []
  let seg = []
  for (let i = 0; i < raw.length; i++) {
    if (i > 0 && raw[i][0] - raw[i - 1][0] > 600) {
      if (seg.length) segments.push(seg)
      seg = []
    }
    seg.push(raw[i])
  }
  if (seg.length) segments.push(seg)

  const total = raw.length
  const timestamps = []
  const values = []
  for (let si = 0; si < segments.length; si++) {
    const seg = segments[si]
    const n = Math.max(2, Math.round(seg.length / total * 200))
    const sampled = seg.length <= 2 ? seg : lttb(seg, n)
    for (const p of sampled) {
      timestamps.push(p[0])
      values.push(p[1])
    }
    // Null gap between segments
    if (si < segments.length - 1) {
      timestamps.push(null)
      values.push(null)
    }
  }
  return [timestamps, values]
}

function valFormatter(v) {
  if (v == null) return '-'
  return fmtNum(v)
}

// 预计算时间戳数组，供二分查找复用
let historyTimestamps = []
function rebuildTimestamps() {
  historyTimestamps = historyData.map(d => new Date(d.timestamp).getTime())
}

// Shared tooltip update — called from setCursor hook on the first chart
function updateTooltip(u) {
  if (u.cursor.left == null || u.cursor.left < 0) {
    ttVisible.value = false
    return
  }
  const ts = u.posToVal(u.cursor.left, 'x') * 1000

  // 二分查找最近的时间戳
  let lo = 0, hi = historyTimestamps.length - 1, closest = null
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1
    if (historyTimestamps[mid] < ts) { lo = mid + 1 }
    else { hi = mid - 1 }
  }
  // lo 是第一个 >= ts 的索引，比较 lo-1 和 lo
  const cand = []
  if (lo > 0) cand.push(lo - 1)
  if (lo < historyTimestamps.length) cand.push(lo)
  let minDiff = Infinity, bestIdx = -1
  for (const idx of cand) {
    const diff = Math.abs(historyTimestamps[idx] - ts)
    if (diff < minDiff) { minDiff = diff; bestIdx = idx }
  }
  if (bestIdx < 0 || minDiff > 120000) { ttVisible.value = false; return }
  closest = historyData[bestIdx]

  ttTime.value = formatTs(closest.timestamp)
  const se = props.scoreEnabled
  ttItems.value = Object.entries(METRICS)
    .filter(([k]) => toggles[k] && (k !== 'score_total' || se))
    .map(([k, m]) => ({
      color: m.color,
      label: m.label,
      value: closest[k] != null ? fmtNum(closest[k]) : '-',
    }))

  const rect = u.root.getBoundingClientRect()
  const tipW = 220
  // 居中于光标竖线，贴近视口边界时自动贴边
  let tx = rect.left + u.cursor.left - tipW / 2
  if (tx < 8) tx = 8
  if (tx + tipW > window.innerWidth - 8) tx = window.innerWidth - tipW - 8
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
      sync: { key: 'charts-sync' },
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
        spanGaps: false,
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
  updateRangeNotice()
  hasData.value = false
  hasIncr.value = false
  try {
    let data
    if (customMode.value) {
      const s = customStart.value
      const e = customEndLive.value ? null : (customEnd.value || null)
      data = await api.getSnapshots(props.selectedId, null, s, e)
    } else {
      data = await api.getSnapshots(props.selectedId, currentH.value)
    }
    historyData = data
    updateRangeNotice()
    hasData.value = data.length > 0
    updateHasIncr()
    rebuildTimestamps()
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
      const visibleKeys = Object.keys(METRICS).filter(k =>
        toggles[k] && (k !== 'score_total' || se) && (k !== 'incr_score_total' || se) && (k !== 'incr_score_total' || hasIncr.value)
      )
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

  // In custom history mode (fixed end), don't append live data
  if (customMode.value && !customEndLive.value) return

  historyData.push({
    timestamp: s.timestamp,
    view_count: s.view_count, danmaku: s.danmaku, reply: s.reply,
    favorite: s.favorite, coin: s.coin, share: s.share, like_count: s.like_count,
    online_total: s.online_total,
    score_play: s.score_play, score_interact: s.score_interact, score_fav: s.score_fav,
    score_coin: s.score_coin, score_like: s.score_like, score_total: s.score_total,
    incr_view_count: s.incr_view_count, incr_danmaku: s.incr_danmaku,
    incr_reply: s.incr_reply, incr_favorite: s.incr_favorite,
    incr_coin: s.incr_coin, incr_like_count: s.incr_like_count,
    incr_share: s.incr_share,
    incr_score_play: s.incr_score_play, incr_score_interact: s.incr_score_interact,
    incr_score_fav: s.incr_score_fav, incr_score_coin: s.incr_score_coin,
    incr_score_like: s.incr_score_like, incr_score_total: s.incr_score_total,
  })

  let cutoffTime
  if (customMode.value) {
    cutoffTime = new Date(customStart.value).getTime()
  } else {
    cutoffTime = Date.now() - currentH.value * 3600 * 1000
  }
  historyData = historyData.filter(d => new Date(d.timestamp).getTime() >= cutoffTime)
  updateRangeNotice()
  hasData.value = historyData.length > 0
  updateHasIncr()
  rebuildTimestamps()
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

if (fmtMode) {
  watch(fmtMode, () => {
    if (historyData.length) renderAll()
  })
}

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
        :class="['range-btn', { active: !customMode && currentH === h }]" @click="setHours(h)"
      >{{ h === 1 ? '1h' : h === 6 ? '6h' : h === 24 ? '24h' : h === 72 ? '3d' : '7d' }}</button>
      <button :class="['range-btn', { active: customMode }]" @click="enterCustom">自定义</button>
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

    <!-- Custom range controls -->
    <div v-if="customMode" class="custom-range">
      <div class="custom-row">
        <div class="custom-field">
          <span class="custom-label">开始</span>
          <DateTimePicker v-model="customStart" placeholder="开始时间" @update:model-value="onCustomParamChange" />
        </div>
        <div class="custom-field">
          <span class="custom-label">结束</span>
          <DateTimePicker v-if="!customEndLive" v-model="customEnd" placeholder="结束时间" @update:model-value="onCustomParamChange" />
          <span v-else class="custom-live-label">实时更新中</span>
        </div>
        <div class="custom-toggle">
          <button
            :class="['live-toggle', { live: customEndLive }]"
            @click="customEndLive = !customEndLive; onCustomParamChange()"
          >{{ customEndLive ? '切换为历史时刻' : '切换为实时' }}</button>
        </div>
      </div>
    </div>

    <div class="charts-scroll" ref="containerRef">
      <div v-if="loading" class="overlay-spinner"><span class="spinner"></span></div>
      <template v-for="[k, m] in visibleMetrics" :key="k">
        <div v-show="toggles[k] && hasData && (k !== 'incr_score_total' || hasIncr)" class="chart-row">
          <div class="row-label">
            <span class="row-dot" :style="{ background: m.color }"></span>
            {{ m.label }}
          </div>
          <div :data-chart="k" class="mini-chart"></div>
        </div>
      </template>
      <div v-if="!loading && hasData && scoreEnabled && toggles.incr_score_total && !hasIncr" class="incr-hint-row">
        <span class="incr-hint-text">未记录到所选时间范围内上周六 03:00 附近的数据，增量得点不可用</span>
      </div>
      <div v-if="!loading && hasData && rangeNotice" class="range-notice">{{ rangeNotice }}</div>
      <div v-if="!loading && !selectedId" class="empty">请选择一个视频开始监控</div>
      <div v-else-if="!loading && !hasData" class="empty">暂无历史数据</div>
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
  background: var(--surface); border-radius: 10px; padding: 14px 18px;
  box-shadow: var(--shadow); display: flex; flex-direction: column;
  -webkit-tap-highlight-color: transparent;
}
.toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.tool-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }

/* Custom range */
.custom-range {
  background: var(--surface-secondary); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;
}
.custom-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.custom-field { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 160px; max-width: 260px; }
.custom-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); white-space: nowrap; flex-shrink: 0; }
.custom-live-label { font-size: 13px; color: var(--accent); font-weight: 500; padding: 8px 0; }
.custom-toggle { flex-shrink: 0; }
.live-toggle {
  border: 1px solid var(--border); background: var(--surface); border-radius: 5px;
  padding: 4px 13px; font-size: 12px; cursor: pointer; font-weight: 500;
  color: var(--text-muted); transition: all .15s; white-space: nowrap;
  -webkit-tap-highlight-color: transparent; outline: none; line-height: 1.5;
}
.live-toggle:hover { border-color: var(--accent); color: var(--accent); }
.live-toggle.live { background: var(--accent); color: #fff; border-color: var(--accent); }
.range-btn {
  border: 1px solid var(--border); background: var(--surface); border-radius: 5px; padding: 4px 13px;
  font-size: 12px; cursor: pointer; font-weight: 500; color: var(--text-muted); transition: all .15s;
  -webkit-tap-highlight-color: transparent; outline: none; line-height: 1.5;
}
.range-btn:hover { border-color: var(--accent); color: var(--accent); }
.range-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.range-btn:focus { outline: none; }
.sep { width: 1px; height: 15px; background: var(--border); margin: 0 5px; }
.tool-group { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.metric-toggle {
  font-size: 12px; display: flex; align-items: center; gap: 4px;
  cursor: pointer; user-select: none; color: var(--text-muted);
  -webkit-tap-highlight-color: transparent; outline: none;
}
.metric-toggle input { position: absolute; opacity: 0; width: 0; height: 0; }
.check-box {
  width: 14px; height: 14px; border: 1.5px solid var(--border); border-radius: 3px;
  transition: all .15s; flex-shrink: 0; position: relative;
}
.metric-toggle input:checked + .check-box { background: var(--accent); border-color: var(--accent); }
.metric-toggle input:checked + .check-box::after {
  content: ''; position: absolute; left: 3px; top: 1px; width: 5px; height: 8px;
  border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg);
}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-left: 2px; }
.charts-scroll { flex: 1; overflow-y: auto; overflow-x: hidden; min-height: 120px; position: relative; -webkit-tap-highlight-color: transparent; }
.chart-row { display: flex; align-items: stretch; margin-bottom: 2px; -webkit-tap-highlight-color: transparent; }
.row-label {
  width: 64px; flex-shrink: 0; display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: var(--text-muted); padding: 4px 0; white-space: nowrap;
}
.row-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.mini-chart { flex: 1; height: 100px; -webkit-tap-highlight-color: transparent; }

.overlay-spinner {
  position: absolute; inset: 0; z-index: 10;
  display: flex; align-items: center; justify-content: center;
}
.spinner {
  width: 28px; height: 28px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty { text-align: center; padding: 40px 0; color: var(--text-placeholder); font-size: 13px; }
.range-notice { text-align: center; padding: 8px 0 4px; color: #c9a84c; font-size: 11px; }
.incr-hint-row {
  display: flex; align-items: center; justify-content: center;
  height: 90px; color: var(--text-placeholder); font-size: 11px;
}
.incr-hint-text { text-align: center; }

.custom-tooltip {
  position: fixed; z-index: 9999;
  background: var(--surface); border-radius: 8px; padding: 10px 14px;
  box-shadow: 0 4px 24px rgba(0,0,0,.12); border: 1px solid var(--border);
  min-width: 160px; max-width: 220px; pointer-events: none; user-select: none;
  white-space: nowrap;
}
.tt-time { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid var(--border-light); }
.tt-row { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; font-size: 12px; }
.tt-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.tt-label { color: var(--text-muted); min-width: 52px; }
.tt-value { color: var(--text); font-weight: 500; }
.tt-fade-enter-active { transition: opacity .12s; }
.tt-fade-leave-active { transition: opacity .1s; }
.tt-fade-enter-from, .tt-fade-leave-to { opacity: 0; }

@media (max-width: 640px) {
  .chart-panel { min-height: 0; }
  .charts-scroll { overflow: visible; }
  .mini-chart { height: 80px; }
  .row-label { width: 42px; font-size: 10px; }
  .toolbar { gap: 4px; }
  .tool-group { gap: 4px; }
  .custom-tooltip { right: 4px; padding: 8px 10px; min-width: 140px; font-size: 11px; }
  .custom-range { padding: 8px 10px; }
  .custom-row { gap: 8px; }
  .custom-field { min-width: 0; flex: 1 1 100%; max-width: none; }
}
</style>

<style>
.u-cursor-y { display: none !important; }
.uplot canvas, .u-over, .u-under { -webkit-tap-highlight-color: transparent; }
</style>
