<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: Object,
})

const emit = defineEmits(['openSettings', 'openManagement'])

const dotClass = computed(() => {
  if (!props.status?.running) return 'dot red'
  return props.status?.last_error ? 'dot red' : 'dot green'
})

function fmtLastFetch(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const msg = computed(() => {
  const s = props.status || {}
  if (!s.running) return '等待配置 · 请添加视频开始监控'
  if (!s.last_fetch) return '运行中 · 等待首轮采集...'
  const prefix = s.last_error ? '异常' : '运行中'
  return `${prefix} · 上次 ${fmtLastFetch(s.last_fetch)}` + (s.last_error ? ` · ${s.last_error}` : '')
})
</script>

<template>
  <header class="header">
    <h1>B站视频数据监控</h1>
    <span :class="dotClass"></span>
    <span class="status-text">{{ msg }}</span>
    <button class="header-btn" @click="emit('openManagement')">管理</button>
    <button class="header-btn" @click="emit('openSettings')">设置</button>
  </header>
</template>

<style scoped>
.header {
  background: var(--surface);
  box-shadow: 0 1px 6px rgba(0,0,0,.05);
  padding: 0 24px;
  height: 50px;
  display: flex;
  align-items: center;
  gap: 14px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header h1 { font-size: 17px; font-weight: 700; letter-spacing: -.3px; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; transition: all .3s; }
.dot.green { background: var(--green); box-shadow: 0 0 8px #22c55e55; }
.dot.red { background: var(--red); box-shadow: 0 0 8px #ef444455; }
.status-text { font-size: 12px; color: var(--text-muted); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.header-btn {
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 7px;
  padding: 6px 16px;
  font-size: 12px;
  cursor: pointer;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all .15s;
}
.header-btn:hover { background: var(--surface-hover); border-color: #ccc; }
@media (max-width: 640px) {
  .header h1 { display: none; }
  .header { padding: 0 12px; gap: 8px; }
}
</style>
