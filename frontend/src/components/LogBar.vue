<script setup>
import { watch, ref, nextTick } from 'vue'

const props = defineProps({ lines: Array, show: Boolean })
const el = ref(null)

function scrollBottom() {
  nextTick(() => {
    if (el.value) el.value.scrollTop = el.value.scrollHeight
  })
}

watch(() => props.lines.length, () => {
  if (!props.show) return
  scrollBottom()
})

watch(() => props.show, (v) => {
  if (v) scrollBottom()
})

function className(line) {
  if (line.includes('HINT')) return 'hint'
  if (line.includes('OK')) return 'ok'
  if (line.includes('FAIL') || line.includes('ERR')) return 'err'
  return 'info'
}
</script>

<template>
  <div :class="['log-bar', { open: show }]" ref="el">
    <div v-if="show" class="log-inner">
      <div v-for="(l, i) in lines" :key="i" :class="['entry', className(l)]">{{ l }}</div>
    </div>
  </div>
</template>

<style scoped>
.log-bar {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 150;
  background: #1e1e2e; font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
  font-size: 11px; color: #cdd6f4; line-height: 1.7;
  height: 0; overflow: hidden; transition: height .25s ease;
}
.log-bar.open { height: 140px; overflow-y: auto; border-top: 2px solid #4f8ef7; }
.log-inner { padding: 8px 16px; }
.entry { white-space: nowrap; }
.entry.ok { color: #a6e3a1; }
.entry.err { color: #f38ba8; }
.entry.info { color: #89b4fa; }
.entry.hint { color: #f9e2af; }
</style>
