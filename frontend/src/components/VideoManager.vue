<script setup>
import { ref, inject } from 'vue'

const props = defineProps({ videos: Array, selectedId: Number })
const emit = defineEmits(['select', 'change'])
const api = inject('api')
const confirmRef = inject('confirm')

const newBvid = ref('')

async function addVideo() {
  const bvid = newBvid.value.trim()
  if (!bvid) return
  try {
    await api.addVideo(bvid)
    newBvid.value = ''
    emit('change')
  } catch (e) {
    // axios 拦截器已弹 toast
  }
}

async function deleteVideo(id) {
  if (!confirmRef?.value) return
  const ok = await confirmRef.value.open('确认删除该视频及其所有数据？')
  if (!ok) return
  await api.deleteVideo(id)
  emit('change')
}
</script>

<template>
  <div class="video-panel">
    <h2>监控视频</h2>
    <div class="add-row">
      <input type="text" v-model="newBvid" placeholder="输入 BV 号添加" @keydown.enter="addVideo" />
      <button @click="addVideo">添加</button>
    </div>
    <div class="video-list">
      <div v-if="!videos.length" class="empty">暂无视频，添加一个开始监控</div>
      <div
        v-for="v in videos" :key="v.id"
        :class="['video-item', { active: v.id === selectedId }]"
        @click="emit('select', v.id)"
      >
        <div class="info">
          <div class="t">{{ v.title || v.bvid }}</div>
          <div class="bv">{{ v.bvid }}</div>
        </div>
        <button class="del-btn" @click.stop="deleteVideo(v.id)" title="删除">&times;</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-panel { background: #fff; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
h2 { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: #333; }
.add-row { display: flex; gap: 8px; margin-bottom: 10px; }
.add-row input { flex: 1; border: 1px solid #e0e0e0; border-radius: 7px; padding: 7px 11px; font-size: 13px; outline: none; transition: border-color .2s; }
.add-row input:focus { border-color: #4f8ef7; box-shadow: 0 0 0 2px #4f8ef720; }
.add-row button { border: none; border-radius: 7px; padding: 7px 16px; font-size: 13px; cursor: pointer; background: #4f8ef7; color: #fff; font-weight: 500; }
.add-row button:hover { background: #3b7de6; }
.video-list { max-height: 300px; overflow-y: auto; }
.video-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; margin-bottom: 1px; transition: background .12s; border: 1px solid transparent; }
.video-item:hover { background: #f8f9fb; }
.video-item.active { background: #eff6ff; border-color: #bfdbfe; }
.info { flex: 1; min-width: 0; }
.info .t { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.info .bv { font-size: 11px; color: #aaa; margin-top: 1px; }
.del-btn { background: none; border: none; color: #ccc; cursor: pointer; font-size: 17px; padding: 2px 5px; line-height: 1; border-radius: 4px; transition: all .15s; }
.del-btn:hover { color: #ef4444; background: #fef2f2; }
.empty { text-align: center; color: #ccc; padding: 24px 0; font-size: 13px; }
</style>
