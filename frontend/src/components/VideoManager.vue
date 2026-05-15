<script setup>
const props = defineProps({ videos: Array, selectedId: Number })
const emit = defineEmits(['select'])
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-panel { background: #fff; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
h2 { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: #333; }
.video-list { max-height: 340px; overflow-y: auto; }
.video-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 1px;
  transition: background .12s; border: 1px solid transparent;
}
.video-item:hover { background: #f8f9fb; }
.video-item.active { background: #eff6ff; border-color: #bfdbfe; }
.video-item.paused { opacity: .65; border-left: 3px solid #f0c040; }
.video-item.paused:hover { opacity: .85; }
.info { flex: 1; min-width: 0; }
.info .t { font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; min-width: 0; }
.t-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.info .bv { font-size: 11px; color: #aaa; margin-top: 1px; }
.pause-badge { font-size: 10px; background: #fef3c7; color: #b88a1e; padding: 1px 6px; border-radius: 3px; font-weight: 500; flex-shrink: 0; white-space: nowrap; }
.empty { text-align: center; color: #ccc; padding: 24px 0; font-size: 13px; }
</style>
