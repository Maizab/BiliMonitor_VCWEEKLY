<script setup>
const props = defineProps({ videos: Array, selectedId: Number })
const emit = defineEmits(['select', 'export'])
</script>

<template>
  <div class="video-panel">
    <h2>监控视频</h2>
    <div class="video-list">
      <div v-if="!videos.length" class="empty">点击右上角「设置」添加视频</div>
      <div
        v-for="v in videos" :key="v.id"
        :class="['video-item', { active: v.id === selectedId, paused: v.paused }]"
        @click="emit('select', v.id)"
      >
        <div class="info">
          <div class="t">
            <span class="t-text">{{ v.title || v.bvid }}</span>
            <span v-if="v.paused" class="pause-badge">⏸ 监控已暂停</span>
          </div>
          <div class="bv">{{ v.bvid }}</div>
        </div>
        <button class="export-btn" @click.stop="emit('export', v)" title="导出数据">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-panel { background: var(--surface); border-radius: 10px; padding: 14px 16px; box-shadow: var(--shadow); }
h2 { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: var(--text); }
.video-list { max-height: 340px; overflow-y: auto; }
.video-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 1px;
  transition: background .12s; border: 1px solid transparent;
}
.video-item:hover { background: var(--surface-hover); }
.video-item.active { background: var(--accent-light); border-color: var(--accent-border); }
.video-item.paused { opacity: .65; border-left: 3px solid #f0c040; }
.video-item.paused:hover { opacity: .85; }
.info { flex: 1; min-width: 0; }
.info .t { font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; min-width: 0; }
.t-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.info .bv { font-size: 11px; color: var(--text-placeholder); margin-top: 1px; }
.pause-badge { font-size: 10px; background: #fef3c7; color: #b88a1e; padding: 1px 6px; border-radius: 3px; font-weight: 500; flex-shrink: 0; white-space: nowrap; }
.export-btn {
  width: 30px; height: 30px; flex-shrink: 0;
  border: none; border-radius: 6px;
  background: transparent; color: var(--text-placeholder); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all .12s;
}
.export-btn:hover { color: var(--accent); }
.empty { text-align: center; color: var(--text-placeholder); padding: 24px 0; font-size: 13px; }
</style>
