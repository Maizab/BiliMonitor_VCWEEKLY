<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: Object,
  showLog: Boolean,
})

const emit = defineEmits(['toggleLog', 'openSettings'])

const dotClass = computed(() => {
  if (!props.status?.running) return 'dot red'
  return props.status?.last_error ? 'dot red' : 'dot green'
})

const msg = computed(() => {
  const s = props.status || {}
  if (!s.running) return '等待配置 · 请添加视频开始监控'
  if (!s.last_fetch) return '运行中 · 等待首轮采集...'
  const prefix = s.last_error ? '异常' : '运行中'
  return `${prefix} · 上次 ${s.last_fetch}` + (s.last_error ? ` · ${s.last_error}` : '')
})
</script>

<template>
  <header class="header">
    <h1>B站视频数据监控</h1>
    <span :class="dotClass"></span>
    <span class="status-text">{{ msg }}</span>
    <button :class="['header-btn', { active: showLog }]" @click="emit('toggleLog')">日志</button>
    <button class="header-btn" @click="emit('openSettings')">设置</button>
  </header>
</template>

<style scoped>
.header {
  background: #fff;
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
.dot.green { background: #22c55e; box-shadow: 0 0 8px #22c55e55; }
.dot.red { background: #ef4444; box-shadow: 0 0 8px #ef444455; }
.status-text { font-size: 12px; color: #888; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.header-btn {
  border: 1px solid #e0e0e0;
  background: #fff;
  border-radius: 7px;
  padding: 6px 16px;
  font-size: 12px;
  cursor: pointer;
  font-weight: 500;
  color: #555;
  transition: all .15s;
}
.header-btn:hover { background: #f5f6f8; border-color: #ccc; }
.header-btn.active { background: #4f8ef7; color: #fff; border-color: #4f8ef7; }
@media (max-width: 640px) {
  .header h1 { display: none; }
  .header { padding: 0 12px; gap: 8px; }
}
</style>
