<script setup>
import { ref, watch, onMounted, onUnmounted, inject, nextTick, reactive } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  selectedId: Number,
  snapshot: Object,
  currentHours: { type: Number, default: 24 },
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

// custom tooltip state
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

// Centered moving average to reduce staircase effect
function smoothSeries(data, key, window = 3) {
  const half = Math.floor(window / 2)
  return data.map((r, i) => {
    let sum = 0, count = 0
    for (let j = Math.max(0, i - half); j < Math.min(data.length, i + half + 1); j++) {
      const v = Number(data[j][key])
      if (!isNaN(v)) { sum += v; count++ }
    }
    return [r.timestamp, count > 0 ? Math.round(sum / count) : null]
  })
}

function makeOption(mKey, m, data) {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      triggerOn: 'mousemove',
      formatter: () => '',
      backgroundColor: 'transparent',
      borderWidth: 0,
      padding: 0,
      extraCssText: 'opacity:0;box-shadow:none;pointer-events:none;',
    },
    grid: { left: 72, right: 16, top: 6, bottom: 2 },
    xAxis: {
      type: 'time',
      show: false,
      axisPointer: {
        lineStyle: { color: '#aaa', width: 1, type: 'dashed' },
        label: { show: false },
      },
    },
    yAxis: {
      type: 'value',
      min: 'dataMin',
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: {
        fontSize: 9, color: '#999',
        formatter: v => v >= 1000000 ? (v/1000000).toFixed(1)+'M' : v >= 1000 ? (v/1000).toFixed(1)+'k' : v,
      },
    },
    series: [{
      type: 'line',
      data: smoothSeries(data, mKey, 11),
      smooth: 0.9, symbol: 'none',
      lineStyle: { color: m.color, width: 1.5 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: m.color + '30' }, { offset: 1, color: m.color + '02' }
        ])
      },
    }],
  }
}

async function loadHistory() {
  if (!props.selectedId) { loading.value = false; return }
  loading.value = true
  Object.values(charts).forEach(c => c.dispose())
  Object.keys(charts).forEach(k => delete charts[k])
  historyData = []
  try {
    const data = await api.getSnapshots(props.selectedId, currentH.value)
    historyData = data
    renderAll()
  } finally {
    loading.value = false
  }
}

// Single custom tooltip via pointermove on container (works for mouse + touch)
let tooltipTimer = null

function hitTest(e) {
  for (const [k, chart] of Object.entries(charts)) {
    if (!toggles[k]) continue
    try {
      const el = chart.getDom()
      const er = el.getBoundingClientRect()
      if (chart.containPixel('grid', [e.clientX - er.left, e.clientY - er.top])) {
        return { chart, key: k }
      }
    } catch (_) { /* ignore */ }
  }
  return null
}

function showTooltipAt(e, isTap) {
  const hit = hitTest(e)
  if (!hit) { ttVisible.value = false; return false }

  const el = hit.chart.getDom()
  const er = el.getBoundingClientRect()
  const point = [e.clientX - er.left, e.clientY - er.top]
  const dataPoint = hit.chart.convertFromPixel({ seriesIndex: 0 }, point)
  if (!dataPoint) { ttVisible.value = false; return false }

  const ts = dataPoint[0]
  let closest = null, closestIdx = -1, minDiff = Infinity
  for (let i = 0; i < historyData.length; i++) {
    const diff = Math.abs(new Date(historyData[i].timestamp).getTime() - ts)
    if (diff < minDiff) { minDiff = diff; closest = historyData[i]; closestIdx = i }
  }

  if (closest && minDiff < 60000) {
    const tipW = 220
    const M = 14
    let tx = e.clientX + M
    if (tx + tipW > window.innerWidth - 4) tx = e.clientX - tipW - M
    if (tx < 4) tx = 4
    if (tx + tipW > window.innerWidth - 4) tx = Math.max(4, window.innerWidth - tipW - 4)
    ttX.value = tx
    ttY.value = e.clientY - 10
    ttVisible.value = true
    ttTime.value = formatTs(closest.timestamp)
    ttItems.value = Object.entries(METRICS)
      .filter(([k]) => toggles[k])
      .map(([k, m]) => ({
        color: m.color,
        label: m.label,
        value: closest[k] != null ? Number(closest[k]).toLocaleString() : '-',
      }))

    // On tap: toggle axisPointer (tap again to dismiss)
    if (isTap) {
      if (axisPointerPinned) {
        ttVisible.value = false
        hideAllTips()
        return false
      }
      hit.chart.dispatchAction({
        type: 'showTip',
        seriesIndex: 0,
        dataIndex: closestIdx,
      })
      axisPointerPinned = true
    }
    return true
  }
  return false
}

let isTouchDevice = false
let axisPointerPinned = false

function onContainerPointer(e) {
  // Detect touch device on first interaction
  if (e.pointerType === 'touch' || e.pointerType === 'pen') isTouchDevice = true

  if (isTouchDevice) {
    // Touch drag: update tooltip position while dragging
    if (ttVisible.value) {
      if (!showTooltipAt(e, false)) ttVisible.value = false
    }
    return
  }

  // Desktop: hover follows mouse
  if (!showTooltipAt(e, false)) ttVisible.value = false
  clearTimeout(tooltipTimer)
}

function hideAllTips() {
  axisPointerPinned = false
  Object.values(charts).forEach(c => {
    c.dispatchAction({ type: 'hideTip' })
  })
}

function onContainerDown(e) {
  if (e.pointerType === 'touch' || e.pointerType === 'pen') {
    isTouchDevice = true
    if (!showTooltipAt(e, true)) hideAllTips()
  }
}

// Dismiss tooltip when tapping outside any chart (touch & pointer)
function dismissIfOutside(e) {
  if (!isTouchDevice) return
  const cx = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0)
  const cy = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0)
  const inside = Object.values(charts).some(c => {
    try {
      const r = c.getDom().getBoundingClientRect()
      return cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom
    } catch (_) { return false }
  })
  if (!inside) {
    ttVisible.value = false
    hideAllTips()
  }
}

function onWindowTouch(e) {
  isTouchDevice = true
  dismissIfOutside(e)
}

function onWindowDown(e) {
  if (e.pointerType !== 'touch' && e.pointerType !== 'pen') return
  dismissIfOutside(e)
}

function onContainerLeave() {
  if (!isTouchDevice) {
    tooltipTimer = setTimeout(() => { ttVisible.value = false }, 150)
  }
}


function initChart(k, m) {
  const el = containerRef.value?.querySelector(`[data-chart="${k}"]`)
  if (!el) return
  if (charts[k]) charts[k].dispose()
  charts[k] = echarts.init(el)
  charts[k].group = 'bili_group'
  charts[k].setOption(makeOption(k, m, historyData))
}

function renderAll() {
  nextTick(() => {
    requestAnimationFrame(() => {
      Object.keys(METRICS).forEach(k => {
        initChart(k, METRICS[k])
      })
      reconnect()
    })
  })
}

function reconnect() {
  echarts.disconnect('bili_group')
  const ids = Object.keys(charts)
  if (ids.length > 1) echarts.connect('bili_group')
}

watch(toggles, (newVal, oldVal) => {
  const changed = Object.keys(METRICS).find(k => newVal[k] !== oldVal?.[k])
  if (!changed) return
  if (newVal[changed]) {
    nextTick(() => {
      if (charts[changed]) charts[changed].resize()
    })
  }
})

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
  Object.entries(METRICS).forEach(([k]) => {
    if (!toggles[k] || !charts[k]) return
    charts[k].setOption({ series: [{ data: smoothSeries(historyData, k, 11) }] })
  })
})

watch(() => props.selectedId, () => {
  Object.values(charts).forEach(c => c.dispose())
  Object.keys(charts).forEach(k => delete charts[k])
  loadHistory()
})

function onResize() {
  Object.values(charts).forEach(c => c.resize())
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  window.addEventListener('pointerdown', onWindowDown)
  window.addEventListener('touchstart', onWindowTouch, { passive: true })
  const el = containerRef.value
  if (el) {
    el.addEventListener('pointermove', onContainerPointer)
    el.addEventListener('pointerdown', onContainerDown)
    el.addEventListener('pointerleave', onContainerLeave)
  }
  nextTick(loadHistory)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('pointerdown', onWindowDown)
  window.removeEventListener('touchstart', onWindowTouch)
  const el = containerRef.value
  if (el) {
    el.removeEventListener('pointermove', onContainerPointer)
    el.removeEventListener('pointerdown', onContainerDown)
    el.removeEventListener('pointerleave', onContainerLeave)
  }
  Object.values(charts).forEach(c => c.dispose())
  echarts.disconnect('bili_group')
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
        <label v-for="(m, k) in METRICS" :key="k" class="metric-toggle">
          <input type="checkbox" v-model="toggles[k]" />
          <span class="check-box"></span>
          <span class="dot" :style="{ background: m.color }"></span>
          {{ m.label }}
        </label>
      </span>
    </div>
    <div class="charts-scroll" ref="containerRef">
      <div v-if="loading" class="overlay-spinner"><span class="spinner"></span></div>
      <template v-for="(m, k) in METRICS" :key="k">
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
    <!-- Single custom tooltip, teleported to body to avoid scroll overflow -->
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
}
.toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.tool-label { font-size: 12px; font-weight: 600; color: #555; }
.range-btn {
  border: 1px solid #e0e0e0; background: #fff; border-radius: 5px; padding: 4px 13px;
  font-size: 12px; cursor: pointer; font-weight: 500; color: #666; transition: all .15s;
}
.range-btn:hover { border-color: #4f8ef7; color: #4f8ef7; }
.range-btn.active { background: #4f8ef7; color: #fff; border-color: #4f8ef7; }
.sep { width: 1px; height: 15px; background: #e8e8e8; margin: 0 5px; }
.tool-group { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.metric-toggle { font-size: 12px; display: flex; align-items: center; gap: 4px; cursor: pointer; user-select: none; color: #666; }
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
.charts-scroll { flex: 1; overflow-y: auto; min-height: 0; position: relative; }
.chart-row { display: flex; align-items: stretch; margin-bottom: 2px; }
.row-label {
  width: 64px; flex-shrink: 0; display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: #666; padding: 4px 0; white-space: nowrap;
}
.row-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.mini-chart { flex: 1; height: 100px; }

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

/* Custom combined tooltip */
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
  .toolbar button, .range-btn, .metric-toggle {
    -webkit-tap-highlight-color: transparent;
    outline: none;
  }
  .toolbar button:focus, .range-btn:focus {
    outline: none;
  }
  .charts-scroll { overflow-y: visible; }
  .mini-chart { height: 70px; }
  .row-label { width: 42px; font-size: 10px; }
  .toolbar { gap: 4px; }
  .tool-group { gap: 4px; }
  .custom-tooltip { right: 4px; padding: 8px 10px; min-width: 140px; font-size: 11px; }
}
</style>
