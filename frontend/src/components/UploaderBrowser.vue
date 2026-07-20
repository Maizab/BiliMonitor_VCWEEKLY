<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { avatarUrl, coverUrls, isCollaboration } from '../utils/imageUrl.js'
import { searchUploaders } from '../composables/useSearch.js'

const props = defineProps({
  uploaders: { type: Array, default: () => [] },
  selectedBvid: { type: String, default: null },
  initialMid: { type: Number, default: null },
})
const emit = defineEmits(['select', 'export'])

// 当前展开的上传者 mid（null 表示在上传者列表视图）
// 用 initialMid 初始化，确保从 URL 恢复时直接展开正确的 UP 主
const expandedMid = ref(props.initialMid)

// 视频列表容器 ref（用于滚动）
const videoListRef = ref(null)

// 搜索
const searchQuery = ref('')

// 当 initialMid 变化时（URL 恢复），展开对应 UP主
watch(() => props.initialMid, (mid) => {
  if (mid) expandedMid.value = mid
})

// 当 selectedBvid 和 uploaders 就绪后，滚动到 active 视频
watch(() => [props.selectedBvid, expandedMid.value], async ([bvid]) => {
  if (!bvid) return
  await nextTick()
  const el = videoListRef.value?.querySelector('.video-item.active')
  if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})

const searchResults = computed(() => {
  if (!searchQuery.value.trim()) return []
  return searchUploaders(props.uploaders, searchQuery.value)
})

const expandedUploader = computed(() => {
  if (!expandedMid.value) return null
  return props.uploaders.find(u => u.mid === expandedMid.value) || null
})

function expandUploader(uploader) {
  expandedMid.value = uploader.mid
  searchQuery.value = ''
}

function goBack() {
  expandedMid.value = null
}

function selectVideo(video) {
  emit('select', { video, uploaderMid: expandedMid.value || video._searchUploaderMid })
}

function onSearchSelect(result) {
  if (result.type === 'uploader') {
    expandUploader({ mid: result.mid, name: result.name, face: result.face, videos: result.videos })
  } else {
    selectVideo(result)
  }
}

// 发布者列表字符串（owner 在前）
function publisherList(uploaders) {
  if (!uploaders || !uploaders.length) return ''
  const sorted = [...uploaders].sort((a, b) => {
    if (a.role === 'owner') return -1
    if (b.role === 'owner') return 1
    return 0
  })
  return sorted.map(u => u.name).join(' / ')
}

// 封面加载失败时显示占位
function onCoverError(e) {
  e.target.style.display = 'none'
  const placeholder = e.target.parentElement?.querySelector('.cover-placeholder')
  if (placeholder) placeholder.style.display = 'flex'
}
</script>

<template>
  <div class="video-panel">
    <h2>查看视频数据</h2>

    <!-- 搜索框 -->
    <div class="search-wrap">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        placeholder="搜索UP主/视频/BV号…"
      />
      <span v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</span>
    </div>

    <div v-if="!uploaders.length && !searchQuery" class="empty">点击右上角「管理」添加视频</div>

    <!-- ===== 搜索结果 ===== -->
    <div v-if="searchQuery.trim()" class="search-results">
      <div v-if="!searchResults.length" class="empty">无匹配结果</div>
      <div v-else class="result-list">
        <!-- UP主结果 -->
        <div
          v-for="r in searchResults.filter(s => s.type === 'uploader')" :key="'u'+r.mid"
          class="search-up-item"
          @click="onSearchSelect(r)"
        >
          <img class="uploader-avatar" :src="avatarUrl(r.face)" referrerpolicy="no-referrer" loading="lazy" />
          <div class="uploader-info">
            <span class="uploader-name">{{ r.name }}</span>
            <span class="uploader-count">{{ r.videoCount }} 个视频</span>
          </div>
          <span class="arrow">›</span>
        </div>
        <!-- 视频结果 -->
        <div
          v-for="r in searchResults.filter(s => s.type === 'video')" :key="'v'+r.id"
          :class="['search-video-item', { active: r.bvid === selectedBvid, paused: r.paused }]"
          @click="onSearchSelect(r)"
        >
          <div class="cover-wrap">
            <picture>
              <source :srcset="coverUrls(r.pic).avif" type="image/avif" />
              <img class="cover-img" :src="coverUrls(r.pic).webp" referrerpolicy="no-referrer" loading="lazy" @error="onCoverError" />
            </picture>
            <div class="cover-placeholder">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            </div>
            <span v-if="isCollaboration(r)" class="collab-badge">合作</span>
          </div>
          <div class="info">
            <div class="t">
              <span class="t-text">{{ r.title }}</span>
              <span v-if="r.paused" class="pause-badge">⏸ 暂停</span>
            </div>
            <div class="bv">{{ r.bvid }}</div>
            <div class="publisher-line">{{ publisherList(r.uploaders) }}</div>
          </div>
          <button class="export-btn" @click.stop="emit('export', r)" title="导出数据">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- ===== 普通浏览（非搜索） ===== -->
    <template v-if="!searchQuery.trim()">
    <!-- 面包屑：浏览上传者的视频时 -->
    <div v-if="expandedUploader" class="breadcrumb">
      <button class="back-btn" @click="goBack">← 返回</button>
      <span class="breadcrumb-title">{{ expandedUploader.name }}</span>
    </div>

    <!-- Level 1: 上传者列表 -->
    <div v-if="!expandedUploader" class="uploader-list">
      <div
        v-for="u in uploaders" :key="u.mid"
        class="uploader-folder"
        @click="expandUploader(u)"
      >
        <img
          class="uploader-avatar"
          :src="avatarUrl(u.face)"
          referrerpolicy="no-referrer"
          loading="lazy"
          @error="e => { e.target.src = 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 48 48%22><rect fill=%22%23e5e7eb%22 width=%2248%22 height=%2248%22/><text x=%2224%22 y=%2230%22 text-anchor=%22middle%22 font-size=%2220%22 fill=%22%239ca3af%22>?</text></svg>' }"
        />
        <div class="uploader-info">
          <span class="uploader-name">{{ u.name }}</span>
          <span class="uploader-count">{{ u.videos.length }} 个视频</span>
        </div>
        <span class="arrow">›</span>
      </div>
    </div>

    <!-- Level 2: 上传者的视频列表 -->
    <div v-if="expandedUploader" ref="videoListRef" class="video-list">
      <div
        v-for="v in expandedUploader.videos" :key="v.id"
        :class="['video-item', { active: v.bvid === selectedBvid, paused: v.paused }]"
        @click="selectVideo(v)"
      >
        <!-- 封面（最左边） -->
        <div class="cover-wrap">
          <picture>
            <source :srcset="coverUrls(v.pic).avif" type="image/avif" />
            <img
              class="cover-img"
              :src="coverUrls(v.pic).webp"
              referrerpolicy="no-referrer"
              loading="lazy"
              @error="onCoverError"
            />
          </picture>
          <div class="cover-placeholder">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          </div>
          <!-- 合作徽章 -->
          <span v-if="isCollaboration(v)" class="collab-badge">合作</span>
        </div>
        <div class="info">
          <div class="t">
            <span class="t-text">{{ v.title || v.bvid }}</span>
            <span v-if="v.paused" class="pause-badge">⏸ 监控已暂停</span>
          </div>
          <div class="bv">{{ v.bvid }}</div>
          <div v-if="v.role && v.role !== 'owner'" class="role-tag">{{ v.role }}</div>
        </div>
        <button class="export-btn" @click.stop="emit('export', v)" title="导出数据">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
      </div>
      <div v-if="!expandedUploader.videos.length" class="empty">暂无视频</div>
    </div>
    </template>
  </div>
</template>

<style scoped>
.video-panel { background: var(--surface); border-radius: 10px; padding: 14px 16px; box-shadow: var(--shadow); }
h2 { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: var(--text); }

/* 面包屑 */
.breadcrumb { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.back-btn {
  border: none; background: none; padding: 3px 8px; font-size: 12px;
  cursor: pointer; color: var(--accent); font-weight: 500; border-radius: 4px;
  transition: background .12s;
}
.back-btn:hover { background: var(--accent-light); }
.breadcrumb-title { font-size: 12px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* 上传者列表 */
.uploader-list { max-height: 340px; overflow-y: auto; }
.uploader-folder {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 1px;
  transition: background .12s;
}
.uploader-folder:hover { background: var(--surface-hover); }
.uploader-avatar {
  width: 36px; height: 36px; border-radius: 50%; object-fit: cover;
  flex-shrink: 0; background: var(--surface-secondary);
}
.uploader-info { flex: 1; min-width: 0; }
.uploader-name { font-size: 13px; font-weight: 500; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.uploader-count { font-size: 11px; color: var(--text-placeholder); }
.arrow { font-size: 16px; color: var(--text-placeholder); flex-shrink: 0; }

/* 视频列表 */
.video-list { max-height: 340px; overflow-y: auto; }
.video-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 1px;
  transition: background .12s; border: 1px solid transparent;
}
.video-item:hover { background: var(--surface-hover); }
.video-item.active { background: var(--accent-light); border-color: var(--accent-border); }
.video-item.paused { opacity: .65; border-left: 3px solid #f0c040; }
.video-item.paused:hover { opacity: .85; }

/* 封面 */
.cover-wrap {
  position: relative; width: 88px; height: 50px; flex-shrink: 0;
  border-radius: 5px; overflow: hidden; background: var(--surface-secondary);
}
.cover-img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}
.cover-placeholder {
  position: absolute; inset: 0; display: none;
  align-items: center; justify-content: center;
  color: var(--text-placeholder); background: var(--surface-secondary);
}

/* 合作徽章 */
.collab-badge {
  position: absolute; top: 3px; right: 3px;
  background: #3b82f6; color: #fff; font-size: 9px; font-weight: 600;
  padding: 1px 5px; border-radius: 3px; line-height: 1.4;
}

/* 视频信息 */
.info { flex: 1; min-width: 0; }
.info .t { font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; min-width: 0; }
.t-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.info .bv { font-size: 11px; color: var(--text-placeholder); margin-top: 1px; }
.pause-badge { font-size: 10px; background: #fef3c7; color: #b88a1e; padding: 1px 6px; border-radius: 3px; font-weight: 500; flex-shrink: 0; white-space: nowrap; }
.role-tag { font-size: 10px; color: var(--accent); margin-top: 2px; }

/* 导出按钮 */
.export-btn {
  width: 30px; height: 30px; flex-shrink: 0;
  border: none; border-radius: 6px;
  background: transparent; color: var(--text-placeholder); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all .12s;
}
.export-btn:hover { color: var(--accent); }

/* 搜索 */
.search-wrap { position: relative; margin-bottom: 10px; }
.search-input {
  width: 100%; border: 1px solid var(--border); border-radius: 7px;
  padding: 6px 28px 6px 10px; font-size: 12px; outline: none;
  background: var(--surface); color: var(--text);
  transition: border-color .2s; box-sizing: border-box;
}
.search-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }
.search-input::placeholder { color: var(--text-placeholder); }
.search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  cursor: pointer; font-size: 13px; color: var(--text-placeholder); line-height: 1;
}
.search-clear:hover { color: var(--text); }
.search-results { max-height: 380px; overflow-y: auto; }
.result-list { /* container */ }
.search-up-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 1px;
  transition: background .12s;
}
.search-up-item:hover { background: var(--surface-hover); }
.search-video-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin-bottom: 1px;
  transition: background .12s; border: 1px solid transparent;
}
.search-video-item:hover { background: var(--surface-hover); }
.search-video-item.active { background: var(--accent-light); border-color: var(--accent-border); }
.search-video-item.paused { opacity: .65; border-left: 3px solid #f0c040; }
.publisher-line {
  font-size: 10px; color: var(--text-muted); margin-top: 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* 空状态 */
.empty { text-align: center; color: var(--text-placeholder); padding: 24px 0; font-size: 13px; }
</style>
