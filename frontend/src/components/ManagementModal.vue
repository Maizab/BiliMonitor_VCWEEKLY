<script setup>
import { ref, inject, watch, nextTick, computed } from 'vue'
import Dropdown from './Dropdown.vue'
import RuleEditModal from './RuleEditModal.vue'
import { avatarUrl } from '../utils/imageUrl.js'
import { searchUploaders } from '../composables/useSearch.js'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['close', 'change'])
const api = inject('api')
const confirmRef = inject('confirm')
const toastRef = inject('toast')
const logLines = inject('logLines', ref([]))

const loading = ref(false)
const loadedOnce = ref(false)

const logBox = ref(null)
const logAutoScroll = ref(true)
const logReady = ref(false)

// Auth
const authReady = ref(false)
const authPassword = ref('')
const authError = ref('')
const authChecking = ref(false)

// Videos
const videos = inject('videos')
const newBvid = ref('')

// Tabs
const activeTab = ref('settings')

// Rule groups
const ruleGroups = ref([])

// Rule group editor state
const selectedGroupId = ref(null)
const selectedGroup = ref(null)

// New group inline input
const newGroupName = ref('')

// Rename inline
const renamingGroupId = ref(null)
const renameText = ref('')

// Rule edit modal
const ruleEditShow = ref(false)
const editingRule = ref(null)  // raw rule from API, or null for add

const RULE_TYPE_LABELS = { 1: '定长', 2: '条件精确', 3: '每天某点', 4: '每周定点' }
const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']

// ---- Timezone conversion (frontend local ↔ backend UTC) ----
function tzOffset() {
  return -new Date().getTimezoneOffset()  // minutes ahead of UTC
}

function toUtcTime(localTime) {
  const [h, m] = localTime.split(':').map(Number)
  const off = tzOffset()
  let mins = h * 60 + m - off
  mins = ((mins % 1440) + 1440) % 1440
  return `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`
}

function toLocalTime(utcTime) {
  const [h, m] = utcTime.split(':').map(Number)
  const off = tzOffset()
  let mins = h * 60 + m + off
  mins = ((mins % 1440) + 1440) % 1440
  return `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`
}

function toUtcDowTime(localDow, localTime) {
  const [h, m] = localTime.split(':').map(Number)
  const off = tzOffset()
  let mins = h * 60 + m - off
  let dayShift = 0
  if (mins < 0) dayShift = -1
  if (mins >= 1440) dayShift = 1
  mins = ((mins % 1440) + 1440) % 1440
  return {
    day_of_week: ((localDow + dayShift) % 7 + 7) % 7,
    time: `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`,
  }
}

function toLocalDowTime(utcDow, utcTime) {
  const [h, m] = utcTime.split(':').map(Number)
  const off = tzOffset()
  let mins = h * 60 + m + off
  let dayShift = 0
  if (mins < 0) dayShift = -1
  if (mins >= 1440) dayShift = 1
  mins = ((mins % 1440) + 1440) % 1440
  return {
    day_of_week: ((utcDow + dayShift) % 7 + 7) % 7,
    time: `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`,
  }
}

const tzLabel = computed(() => {
  const off = tzOffset()
  const sign = off >= 0 ? '+' : '-'
  const h = Math.abs(Math.floor(off / 60))
  const m = Math.abs(off % 60)
  return m ? `UTC${sign}${h}:${String(m).padStart(2, '0')}` : `UTC${sign}${h}`
})

const METRIC_OPTIONS = [
  { value: 'view_count', label: '播放量' },
  { value: 'danmaku', label: '弹幕' },
  { value: 'reply', label: '评论' },
  { value: 'favorite', label: '收藏' },
  { value: 'coin', label: '硬币' },
  { value: 'share', label: '分享' },
  { value: 'like_count', label: '点赞' },
  { value: 'online_total', label: '在线人数' },
  { value: 'score_play', label: '得点(播放)' },
  { value: 'score_interact', label: '得点(互动)' },
  { value: 'score_fav', label: '得点(收藏)' },
  { value: 'score_coin', label: '得点(硬币)' },
  { value: 'score_like', label: '得点(点赞)' },
  { value: 'score_total', label: '得点(总分)' },
  { value: 'incr_view_count', label: '增量播放' },
  { value: 'incr_danmaku', label: '增量弹幕' },
  { value: 'incr_reply', label: '增量评论' },
  { value: 'incr_favorite', label: '增量收藏' },
  { value: 'incr_coin', label: '增量硬币' },
  { value: 'incr_share', label: '增量分享' },
  { value: 'incr_like_count', label: '增量点赞' },
]

const RULE_TYPE_OPTIONS = [
  { value: 1, label: '定长' },
  { value: 2, label: '条件精确' },
  { value: 3, label: '每天某点' },
  { value: 4, label: '每周定点' },
]

const DOW_OPTIONS = [
  { value: 0, label: '周一' }, { value: 1, label: '周二' },
  { value: 2, label: '周三' }, { value: 3, label: '周四' },
  { value: 4, label: '周五' }, { value: 5, label: '周六' },
  { value: 6, label: '周日' },
]

// ---- Log scroll ----
watch(logLines, () => {
  if (logAutoScroll.value && logBox.value) {
    nextTick(() => {
      const el = logBox.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }
}, { deep: true })

function onLogScroll() {
  if (!logBox.value) return
  const el = logBox.value
  logAutoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 30
}

// ---- Load ----
async function loadCfg() {
  if (!loadedOnce.value) loading.value = true
  try {
    videos.value = await api.getVideos()
    ruleGroups.value = await api.getRuleGroups()
  } catch (e) { /* ignore */ }
  loading.value = false
  loadedOnce.value = true
}

// ---- Auth ----
async function doVerify() {
  authError.value = ''
  authChecking.value = true
  try {
    await api.verifyPassword(authPassword.value)
    sessionStorage.setItem('auth-password', authPassword.value)
    authReady.value = true
    await loadCfg()
  } catch (e) {
    authError.value = '密码错误'
  }
  authChecking.value = false
}

watch(() => props.show, async (v) => {
  if (v) {
    authPassword.value = ''
    authError.value = ''
    selectedGroupId.value = null; selectedGroup.value = null
    ruleEditShow.value = false; editingRule.value = null
    newGroupName.value = ''
    renamingGroupId.value = null; renameText.value = ''

    const cached = sessionStorage.getItem('auth-password')
    if (cached) {
      authChecking.value = true
      try {
        await api.verifyPassword(cached)
        authReady.value = true
      } catch (e) {
        sessionStorage.removeItem('auth-password')
        authReady.value = false
        toastRef?.value?.show('本地存储的密码可能无效或管理密码已被更改', 'error')
        try {
          const check = await api.getAuthCheck()
          if (!check.protected) authReady.value = true
        } catch (_) { /* ignore */ }
      }
      authChecking.value = false
    } else {
      try {
        const check = await api.getAuthCheck()
        authReady.value = !check.protected
      } catch (e) { authReady.value = true }
    }
    logReady.value = false
    nextTick(() => {
      if (logBox.value) {
        logBox.value.scrollTop = logBox.value.scrollHeight
        logReady.value = true
      }
    })
    if (authReady.value) await loadCfg()
  }
})

// ---- Video management ----
const BVID_RE = /^BV[1-9A-HJ-NP-Za-km-z]{10}$/

async function addVideo() {
  const bvid = newBvid.value.trim()
  if (!bvid) return
  if (!BVID_RE.test(bvid)) {
    toastRef?.value?.show('无效的 BV 号格式', 'error')
    return
  }
  try {
    await api.addVideo(bvid)
    newBvid.value = ''
    videos.value = await api.getVideos()
    emit('change')
  } catch (e) { /* ignore */ }
}

async function deleteVideo(id) {
  if (!confirmRef?.value) return
  const ok = await confirmRef.value.open('确认删除该视频及其所有历史数据？')
  if (!ok) return
  await api.deleteVideo(id)
  videos.value = await api.getVideos()
  emit('change')
}

async function togglePaused(v) {
  await api.togglePaused(v.id, !v.paused)
  videos.value = await api.getVideos()
  emit('change')
}

async function toggleScore(v) {
  if (!confirmRef?.value) return
  const warning = v.score_enabled
    ? '关闭后将删除该视频所有已计算的得点数据，确定继续？'
    : '开启后将重新计算该视频所有历史数据的得点，可能需要一些时间，确定继续？'
  const ok = await confirmRef.value.open(warning, v.score_enabled ? '确认关闭' : '确认开启')
  if (!ok) return
  v.score_enabled = !v.score_enabled
  try {
    await api.toggleScore(v.id, v.score_enabled)
    videos.value = await api.getVideos()
  } catch (e) { v.score_enabled = !v.score_enabled }
  emit('change')
}

async function assignRuleGroup(videoId, groupId) {
  // 乐观更新：瞬间改本地显示
  const video = videos.value.find(v => v.id === videoId)
  if (video) video.rule_group_id = groupId
  // 也更新分组视图里的数据
  for (const u of uploaders.value) {
    const v = u.videos?.find(v => v.id === videoId)
    if (v) v.rule_group_id = groupId
  }
  try {
    await api.assignVideoRule(videoId, groupId)
    toastRef?.value?.show('规则组已切换', 'success')
  } catch (e) { /* ignore */ }
  // 用后端数据覆盖，保证一致性
  videos.value = await api.getVideos()
}

function fmtTs(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Only for video table dropdown: map groups to {value, label}
const groupOptions = () => ruleGroups.value.map(g => ({ value: g.id, label: g.name }))

const detailLoading = ref(false)

// ---- Rule group management ----
async function selectGroup(id) {
  selectedGroupId.value = id
  closeRuleEdit()
  detailLoading.value = true
  try {
    selectedGroup.value = await api.getRuleGroup(id)
  } catch (e) { selectedGroup.value = null }
  detailLoading.value = false
}

async function doCreateGroup() {
  const name = newGroupName.value.trim()
  if (!name) return
  try {
    await api.createRuleGroup(name)
    newGroupName.value = ''
    await refreshGroups()
    toastRef?.value?.show('规则组已创建', 'success')
  } catch (e) { /* ignore */ }
}

function startRename(g) {
  renamingGroupId.value = g.id
  renameText.value = g.name
}

async function doRename(g) {
  const name = renameText.value.trim()
  if (!name || name === g.name) { renamingGroupId.value = null; return }
  try {
    await api.updateRuleGroup(g.id, name)
    await refreshGroups()
    if (selectedGroupId.value === g.id) {
      selectedGroup.value = await api.getRuleGroup(g.id)
    }
    toastRef?.value?.show('已重命名', 'success')
  } catch (e) { /* ignore */ }
  renamingGroupId.value = null
}

async function deleteGroup(g) {
  if (!confirmRef?.value) return
  const isDefault = g.id === Math.min(...ruleGroups.value.map(x => x.id))
  if (isDefault) {
    toastRef?.value?.show('不能删除默认规则组', 'error')
    return
  }
  const ok = await confirmRef.value.open(
    `删除「${g.name}」后，关联的视频将移回默认组。确认删除？`, '确认删除'
  )
  if (!ok) return
  try {
    await api.deleteRuleGroup(g.id)
    if (selectedGroupId.value === g.id) {
      selectedGroupId.value = null; selectedGroup.value = null
    }
    await refreshGroups()
    emit('change')
    toastRef?.value?.show('规则组已删除', 'success')
  } catch (e) { /* ignore */ }
}

async function refreshGroups() {
  const [groups, vids] = await Promise.all([
    api.getRuleGroups(),
    api.getVideos(),
  ])
  ruleGroups.value = groups
  videos.value = vids
}

// ---- Rule editor ----
const ruleEditForm = computed(() => {
  // Build the form data for RuleEditModal from the stored rule
  if (!editingRule.value) return null
  const r = editingRule.value
  try {
    const v = typeof r.value === 'string' ? JSON.parse(r.value) : r.value
    if (r.rule_type === 1) return { rule_type: 1, interval: v.interval || 60 }
    if (r.rule_type === 2) return {
      rule_type: 2, metric: v.metric || 'view_count',
      min_value: v.min_value ?? null, max_value: v.max_value ?? null,
      target_interval: v.target_interval || 30,
    }
    if (r.rule_type === 3) return { rule_type: 3, time: toLocalTime(v.time || '00:00') }
    if (r.rule_type === 4) {
      const l = toLocalDowTime(v.day_of_week ?? 4, v.time || '19:00')
      return { rule_type: 4, day_of_week: l.day_of_week, time: l.time }
    }
  } catch (e) { /* ignore */ }
  return { rule_type: 1, interval: 60 }
})

function startAddRule() {
  editingRule.value = null
  ruleEditShow.value = true
}

function startEditRule(rule) {
  editingRule.value = rule
  ruleEditShow.value = true
}

async function onRuleSaved({ type, value }) {
  // 转换为 UTC 时间
  let finalValue = value
  if (type === 3) {
    finalValue = { time: toUtcTime(value.time) }
  } else if (type === 4) {
    const u = toUtcDowTime(value.day_of_week, value.time)
    finalValue = { day_of_week: u.day_of_week, time: u.time }
  }

  const isEdit = !!editingRule.value
  const editRuleId = editingRule.value?.id
  const gid = selectedGroupId.value
  const prevGroup = selectedGroup.value ? { ...selectedGroup.value, rules: [...(selectedGroup.value.rules || [])] } : null

  // 乐观更新：先改本地数据
  const jsonValue = JSON.stringify(finalValue)
  if (selectedGroup.value?.rules) {
    if (isEdit) {
      const idx = selectedGroup.value.rules.findIndex(r => r.id === editRuleId)
      if (idx !== -1) {
        selectedGroup.value.rules[idx] = { ...selectedGroup.value.rules[idx], rule_type: type, value: jsonValue }
      }
    } else {
      const tempRule = { id: -Date.now(), group_id: gid, rule_type: type, value: jsonValue, position: 999, created_at: '' }
      selectedGroup.value.rules = [...selectedGroup.value.rules, tempRule]
    }
  }

  ruleEditShow.value = false
  editingRule.value = null

  try {
    if (isEdit) {
      await api.updateRule(editRuleId, type, finalValue)
    } else {
      await api.addRule(gid, type, finalValue)
    }
    const [group] = await Promise.all([
      api.getRuleGroup(gid),
      refreshGroups(),
    ])
    selectedGroup.value = group
    emit('change')
    toastRef?.value?.show('规则已保存', 'success')
  } catch (e) {
    // 失败时恢复旧数据
    if (prevGroup) selectedGroup.value = prevGroup
  }
}

function closeRuleEdit() {
  ruleEditShow.value = false
  editingRule.value = null
}

async function deleteRuleById(ruleId) {
  if (!confirmRef?.value) return
  const ok = await confirmRef.value.open('确认删除该规则？', '确认删除')
  if (!ok) return
  if (selectedGroup.value?.rules) {
    selectedGroup.value.rules = selectedGroup.value.rules.filter(r => r.id !== ruleId)
  }
  try {
    await api.deleteRule(ruleId)
    await refreshGroups()
    emit('change')
    toastRef?.value?.show('规则已删除', 'success')
  } catch (e) {
    if (selectedGroupId.value) {
      selectedGroup.value = await api.getRuleGroup(selectedGroupId.value)
    }
  }
}

function ruleSummary(rule) {
  try {
    const v = typeof rule.value === 'string' ? JSON.parse(rule.value) : rule.value
    if (rule.rule_type === 1) return `每 ${v.interval}s`
    if (rule.rule_type === 2) {
      const opt = METRIC_OPTIONS.find(m => m.value === v.metric)
      const label = opt ? opt.label : v.metric
      const lo = v.min_value != null ? `${v.min_value} ≤ ` : ''
      const hi = v.max_value != null ? ` ≤ ${v.max_value}` : ''
      return `${lo}${label}${hi} → ${v.target_interval}s`
    }
    if (rule.rule_type === 3) return `每天 ${toLocalTime(v.time)} (${tzLabel.value})`
    if (rule.rule_type === 4) {
      const l = toLocalDowTime(v.day_of_week ?? 4, v.time || '19:00')
      return `每周${WEEKDAY_NAMES[l.day_of_week]} ${l.time} (${tzLabel.value})`
    }
  } catch (e) { return '-' }
  return '-'
}

// 按上传者分组的视频数据（前端计算）
const uploaders = inject('uploaders', ref([]))

const uploaderGroups = computed(() => {
  // 如果没有 uploaders 数据，从 videos 的 uploaders 字段构建
  if (uploaders.value && uploaders.value.length) return uploaders.value
  const map = new Map()
  for (const v of videos.value) {
    const vuploaders = v.uploaders || []
    for (const u of vuploaders) {
      if (!map.has(u.mid)) {
        map.set(u.mid, { mid: u.mid, name: u.name, face: u.face, videos: [] })
      }
      map.get(u.mid).videos.push(v)
    }
  }
  return Array.from(map.values())
})

// 管理页面内的上传者展开状态
const mgmtExpandedMid = ref(null)

// 展开的UP主视频全部被删除时，自动回到UP主列表
watch(() => {
  if (!mgmtExpandedMid.value) return
  const u = uploaderGroups.value.find(g => g.mid === mgmtExpandedMid.value)
  return u?.videos?.length || 0
}, (count) => {
  if (count === 0) mgmtExpandedMid.value = null
})

// 管理页面搜索
const mgmtSearchQuery = ref('')

const mgmtSearchResults = computed(() => {
  if (!mgmtSearchQuery.value.trim()) return []
  return searchUploaders(uploaderGroups.value, mgmtSearchQuery.value)
})

function mgmtExpandUploader(uploader) {
  mgmtExpandedMid.value = uploader.mid
}

// 发布者列表（owner 在前）
function publisherList(uploaders) {
  if (!uploaders || !uploaders.length) return ''
  const sorted = [...uploaders].sort((a, b) => {
    if (a.role === 'owner') return -1
    if (b.role === 'owner') return 1
    return 0
  })
  return sorted.map(u => u.name).join(' / ')
}

function isDefaultGroup(g) {
  if (!ruleGroups.value.length) return false
  return g.id === Math.min(...ruleGroups.value.map(x => x.id))
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay">
        <div class="modal-box">
          <h2>管理</h2>

          <!-- Password -->
          <div v-if="!authReady" class="auth-box">
            <p class="auth-label">请输入密码以使用完整管理功能</p>
            <form class="auth-row" @submit.prevent="doVerify">
              <input type="password" v-model="authPassword" placeholder="密码" :disabled="authChecking" />
              <button class="btn-save" type="submit" :disabled="authChecking">
                {{ authChecking ? '验证中...' : '确认' }}
              </button>
            </form>
            <p v-if="authError" class="auth-error">{{ authError }}</p>
          </div>

          <template v-else>
            <div v-if="loading" class="cfg-spinner"><span class="spinner"></span></div>
            <template v-else>
              <!-- Tabs -->
              <div class="tab-bar">
                <button :class="['tab-btn', { active: activeTab === 'settings' }]" @click="activeTab = 'settings'">采集设置</button>
                <button :class="['tab-btn', { active: activeTab === 'rules' }]" @click="activeTab = 'rules'">规则组管理</button>
              </div>

              <!-- ========== Tab: 采集设置 ========== -->
              <template v-if="activeTab === 'settings'">
                <section class="section">
                  <h3>监控视频 <span class="count">({{ videos.length }})</span></h3>
                  <div class="add-row">
                    <input type="text" v-model="newBvid" placeholder="输入 BV 号添加" @keydown.enter="addVideo" />
                    <button class="btn-add" @click="addVideo">添加</button>
                  </div>

                  <!-- 搜索 -->
                  <div class="mgmt-search-wrap">
                    <input type="text" v-model="mgmtSearchQuery" class="mgmt-search-input" placeholder="搜索UP主/视频/BV号…" />
                    <span v-if="mgmtSearchQuery" class="search-clear" @click="mgmtSearchQuery = ''">✕</span>
                  </div>

                  <!-- ===== 搜索结果（直接可操作） ===== -->
                  <div v-if="mgmtSearchQuery.trim()" class="mgmt-search-results">
                    <div v-if="!mgmtSearchResults.length" class="empty-hint">无匹配结果</div>
                    <template v-else>
                      <!-- UP主命中：作为分组标题，下列出其所有视频 -->
                      <template v-for="r in mgmtSearchResults.filter(s => s.type === 'uploader')" :key="'su'+r.mid">
                        <div class="search-up-header" @click="mgmtSearchQuery = ''; mgmtExpandedMid = r.mid">
                          <img class="mgmt-up-avatar" :src="avatarUrl(r.face)" referrerpolicy="no-referrer" />
                          <span class="search-up-name">{{ r.name }}</span>
                          <span class="search-up-count">{{ r.videoCount }} 个视频</span>
                          <span class="arrow">›</span>
                        </div>
                      </template>
                      <!-- 视频结果（表格行，直接操作） -->
                      <div class="video-table-wrap" style="max-height:none;">
                        <table class="video-table">
                          <thead>
                            <tr>
                              <th class="col-title">视频</th>
                              <th class="col-group">规则组</th>
                              <th class="col-count">数据</th>
                              <th class="col-time">最后更新</th>
                              <th class="col-actions">操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="v in mgmtSearchResults.filter(s => s.type === 'video')" :key="'sv'+v.id" :class="{ paused: v.paused }">
                              <td class="col-title">
                                <div class="v-title">{{ v.title }}</div>
                                <div class="v-bvid">{{ v.bvid }}</div>
                                <div class="v-pub" style="font-size:10px;color:var(--text-muted);">{{ publisherList(v.uploaders) }}</div>
                              </td>
                              <td class="col-group">
                                <Dropdown
                                  :options="groupOptions()"
                                  :modelValue="v.rule_group_id"
                                  @update:modelValue="assignRuleGroup(v.id, $event)"
                                />
                              </td>
                              <td class="col-count">{{ v.snapshot_count || 0 }}</td>
                              <td class="col-time">{{ fmtTs(v.last_snapshot_at) }}</td>
                              <td class="col-actions">
                                <button :class="['btn-sm', v.paused ? 'btn-resume' : 'btn-pause']"
                                  :title="v.paused ? '继续采集' : '暂停采集'"
                                  @click="togglePaused(v)">{{ v.paused ? '继续' : '暂停' }}</button>
                                <button :class="['btn-sm', v.score_enabled ? 'btn-score-on' : 'btn-score-off']"
                                  :title="v.score_enabled ? '关闭得点' : '得点已关闭'"
                                  @click="toggleScore(v)">得点</button>
                                <button class="btn-sm btn-del" @click="deleteVideo(v.id)" title="删除">删除</button>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </template>
                  </div>

                  <!-- ===== 分组视图 ===== -->
                  <!-- UP主分组视图（始终显示） -->
                  <div v-if="!mgmtSearchQuery.trim()" class="mgmt-uploader-groups">
                    <!-- 面包屑 -->
                    <div v-if="mgmtExpandedMid" class="mgmt-breadcrumb">
                      <button class="back-btn" @click="mgmtExpandedMid = null">← 返回UP主列表</button>
                    </div>
                    <!-- UP主列表 -->
                    <div v-if="!mgmtExpandedMid" class="mgmt-up-list">
                      <div v-for="u in uploaderGroups" :key="u.mid" class="mgmt-up-item" @click="mgmtExpandUploader(u)">
                        <img class="mgmt-up-avatar" :src="avatarUrl(u.face)" referrerpolicy="no-referrer" @error="e => { e.target.style.display='none' }" />
                        <div class="mgmt-up-info">
                          <span class="mgmt-up-name">{{ u.name }}</span>
                          <span class="mgmt-up-count">{{ u.videos.length }} 个视频</span>
                        </div>
                        <span class="arrow">›</span>
                      </div>
                      <div v-if="!uploaderGroups.length" class="empty-hint">暂无视频</div>
                    </div>
                    <!-- UP主下的视频表 -->
                    <div v-else class="video-table-wrap">
                      <table class="video-table">
                        <thead>
                          <tr>
                            <th class="col-title">视频</th>
                            <th class="col-group">规则组</th>
                            <th class="col-count">数据条数</th>
                            <th class="col-time">最后更新</th>
                            <th class="col-actions">操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="v in (uploaderGroups.find(u => u.mid === mgmtExpandedMid)?.videos || [])" :key="v.id" :class="{ paused: v.paused }">
                            <td class="col-title">
                              <div class="v-title">{{ v.title || v.bvid }}</div>
                              <div class="v-bvid">{{ v.bvid }}</div>
                            </td>
                            <td class="col-group">
                              <Dropdown
                                :options="groupOptions()"
                                :modelValue="v.rule_group_id"
                                @update:modelValue="assignRuleGroup(v.id, $event)"
                              />
                            </td>
                            <td class="col-count">{{ v.snapshot_count || 0 }}</td>
                            <td class="col-time">{{ fmtTs(v.last_snapshot_at) }}</td>
                            <td class="col-actions">
                              <button :class="['btn-sm', v.paused ? 'btn-resume' : 'btn-pause']"
                                :title="v.paused ? '继续采集' : '暂停采集'"
                                @click="togglePaused(v)">{{ v.paused ? '继续' : '暂停' }}</button>
                              <button :class="['btn-sm', v.score_enabled ? 'btn-score-on' : 'btn-score-off']"
                                :title="v.score_enabled ? '关闭得点' : '得点已关闭'"
                                @click="toggleScore(v)">得点</button>
                              <button class="btn-sm btn-del" @click="deleteVideo(v.id)" title="删除">删除</button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                </section>
              </template>

              <!-- ========== Tab: 规则组管理 ========== -->
              <template v-if="activeTab === 'rules'">
                <div class="layout">
                  <!-- 左侧：规则组列表（桌面端始终显示，移动端选中后隐藏） -->
                  <div class="group-panel" :class="{ 'mobile-hidden': selectedGroupId }">
                    <div class="panel-header">
                      <span class="panel-title">规则组</span>
                    </div>
                    <div class="panel-body">
                      <div v-for="g in ruleGroups" :key="g.id"
                        :class="['group-item', { active: g.id === selectedGroupId }]"
                        @click="selectGroup(g.id)">
                        <div class="group-main">
                          <template v-if="renamingGroupId === g.id">
                            <input class="rename-input" v-model="renameText"
                              @keydown.enter="doRename(g)" @keydown.escape="renamingGroupId = null"
                              @click.stop @blur="doRename(g)" autofocus />
                          </template>
                          <template v-else>
                            <div class="group-name">{{ g.name }}</div>
                            <div class="group-meta">{{ g.rules_count }} 条规则</div>
                          </template>
                        </div>
                        <div class="group-actions" @click.stop>
                          <button class="btn-icon" title="重命名" @click="startRename(g)">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                          </button>
                          <button class="btn-icon btn-danger" title="删除"
                            :disabled="isDefaultGroup(g)" @click="deleteGroup(g)">✕</button>
                        </div>
                      </div>
                      <div v-if="!ruleGroups.length" class="empty-hint">暂无规则组</div>
                    </div>
                    <!-- 新建组 -->
                    <div class="panel-footer">
                      <input class="new-group-input" v-model="newGroupName" placeholder="规则组名称"
                        @keydown.enter="doCreateGroup" />
                      <button class="btn-save-sm" @click="doCreateGroup">添加</button>
                    </div>
                  </div>

                  <!-- 右侧：组详情（桌面端始终显示，移动端选中后全屏） -->
                  <div class="detail-panel" :class="{ 'mobile-full': selectedGroupId }">
                    <!-- 移动端返回按钮 -->
                    <button class="mobile-back-btn" @click="selectedGroupId = null; selectedGroup = null">← 返回规则组列表</button>
                    <Transition name="detail-fade" mode="out-in">
                      <div v-if="detailLoading" key="loading" class="detail-loading"><span class="spinner"></span></div>
                      <div v-else-if="selectedGroup" :key="selectedGroupId" class="detail-inner">
                      <div class="detail-header">
                        <h3>{{ selectedGroup.name }} — 规则列表</h3>
                        <button class="btn-add-sm" @click="startAddRule">+ 添加规则</button>
                      </div>

                      <!-- 规则列表 -->
                      <div class="rules-list">
                        <div v-if="!selectedGroup.rules?.length" class="empty-hint">空规则组 — 默认每 60 秒采集一次</div>
                        <div v-for="r in selectedGroup.rules" :key="r.id" class="rule-item">
                          <div class="rule-info">
                            <span :class="['rule-tag', `type-${r.rule_type}`]">{{ RULE_TYPE_LABELS[r.rule_type] }}</span>
                            <span class="rule-summary">{{ ruleSummary(r) }}</span>
                          </div>
                          <div class="rule-actions">
                            <button class="btn-sm" @click="startEditRule(r)">编辑</button>
                            <button class="btn-sm btn-del" @click="deleteRuleById(r.id)">删除</button>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-else key="empty" class="empty-hint detail-empty">← 选择一个规则组查看详情</div>
                    </Transition>
                  </div>
                </div>
              </template>
            </template>
          </template>

          <!-- 规则编辑弹窗 -->
          <RuleEditModal
            :show="ruleEditShow"
            :rule="ruleEditForm"
            :ruleTypeOptions="RULE_TYPE_OPTIONS"
            :metricOptions="METRIC_OPTIONS"
            :dowOptions="DOW_OPTIONS"
            @close="closeRuleEdit"
            @save="onRuleSaved"
          />

          <!-- 日志 -->
          <section class="section log-section">
            <h3>运行日志</h3>
            <div class="log-box" ref="logBox" @scroll="onLogScroll" :style="{ visibility: logReady ? 'visible' : 'hidden' }">
              <div v-if="!logLines.length" class="log-empty">暂无日志</div>
              <div v-for="(line, i) in logLines" :key="i" :class="['log-line', line.includes('OK') ? 'log-ok' : line.includes('FAIL') || line.includes('ERR') ? 'log-err' : '']">{{ line }}</div>
            </div>
          </section>

          <div class="actions">
            <button class="btn-primary" @click="emit('close')">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 200;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 6vh;
  background: var(--overlay); backdrop-filter: blur(3px);
  overflow-y: auto;
}
.modal-box {
  background: var(--surface); border-radius: 14px; padding: 24px 28px;
  width: 820px; max-width: 96vw;
  box-shadow: var(--shadow-lg); position: relative;
}
h2 { font-size: 17px; font-weight: 700; margin-bottom: 16px; }

.auth-box { padding: 10px 0 24px; }
.auth-label { font-size: 13px; color: var(--text-secondary); margin-bottom: 10px; }
.auth-row { display: flex; gap: 8px; align-items: center; }
.auth-row input { flex: 1; border: 1px solid var(--border); border-radius: 7px; padding: 7px 11px; font-size: 13px; outline: none; background: var(--surface); color: var(--text); transition: border-color .2s; }
.auth-row input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }
.auth-error { font-size: 12px; color: var(--red); margin-top: 8px; }

.cfg-spinner { display: flex; align-items: center; justify-content: center; padding: 40px 0; }
.cfg-spinner .spinner { width: 24px; height: 24px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Tabs */
.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid var(--border-light); }
.tab-btn {
  border: none; background: none; padding: 7px 16px; font-size: 13px;
  cursor: pointer; font-weight: 500; color: var(--text-muted);
  border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all .15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

.section { margin-bottom: 20px; }
.section h3 { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 10px; }
.count { font-weight: 400; color: var(--text-placeholder); }

/* Video table */
.add-row { display: flex; gap: 8px; margin-bottom: 10px; }
.add-row input { flex: 1; border: 1px solid var(--border); border-radius: 7px; padding: 7px 11px; font-size: 13px; outline: none; background: var(--surface); color: var(--text); transition: border-color .2s; }
.add-row input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }

.video-table-wrap { max-height: 320px; overflow-y: auto; border: 1px solid var(--border-light); border-radius: 8px; }
.video-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.video-table th { position: sticky; top: 0; z-index: 1; background: var(--surface-secondary); padding: 8px 10px; text-align: left; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-light); white-space: nowrap; }
.video-table td { padding: 8px 10px; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
.video-table tbody tr:hover { background: var(--surface-hover); }
.video-table tbody tr.paused { opacity: .55; }
.video-table tbody tr.paused:hover { opacity: .75; }

.col-title { min-width: 150px; }
.col-group { width: 100px; }
.col-count { width: 50px; text-align: center; color: var(--text-muted); }
.col-time { width: 110px; white-space: nowrap; color: var(--text-muted); }
.col-actions { width: 140px; white-space: nowrap; text-align: right; }

.v-title { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px; }
.v-bvid { font-size: 11px; color: var(--text-placeholder); }

/* Layout for rule group tab */
.layout { display: flex; gap: 16px; min-height: 340px; }

/* Group panel */
.group-panel { width: 200px; flex-shrink: 0; border: 1px solid var(--border-light); border-radius: 8px; display: flex; flex-direction: column; }
.panel-header { padding: 10px 12px; border-bottom: 1px solid var(--border-light); }
.panel-title { font-size: 12px; font-weight: 600; color: var(--text-muted); }
.panel-body { flex: 1; overflow-y: auto; padding: 4px; }
.panel-footer { padding: 6px; border-top: 1px solid var(--border-light); display: flex; gap: 4px; }

.group-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 7px 8px; border-radius: 6px; cursor: pointer; transition: background .12s; font-size: 12px;
}
.group-item:hover { background: var(--surface-hover); }
.group-item.active { background: var(--accent-light); }
.group-main { flex: 1; min-width: 0; }
.group-name { font-weight: 500; }
.group-meta { font-size: 10px; color: var(--text-placeholder); margin-top: 1px; }
.group-actions { display: flex; gap: 1px; flex-shrink: 0; margin-left: 4px; }
.rename-input { width: 100%; border: 1px solid var(--accent); border-radius: 4px; padding: 3px 6px; font-size: 12px; outline: none; }

.new-group-input { width: 110px; border: 1px solid var(--border); border-radius: 5px; padding: 5px 7px; font-size: 12px; outline: none; background: var(--surface); color: var(--text); }
.new-group-input:focus { border-color: var(--accent); }

.btn-icon {
  border: none; background: none; cursor: pointer; font-size: 12px;
  padding: 2px 4px; border-radius: 3px; color: var(--text-muted); transition: all .12s;
}
.btn-icon:hover { background: var(--surface-hover); color: var(--text); }
.btn-icon:disabled { opacity: .3; cursor: not-allowed; }
.btn-icon.btn-danger:hover { color: var(--red); background: #fef2f2; }

/* Detail panel */
.detail-panel { flex: 1; min-width: 0; }
.detail-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.detail-header h3 { font-size: 13px; font-weight: 600; color: var(--text); margin: 0; }

/* Rule form */
.rule-form {
  background: var(--surface-secondary); border: 1px solid var(--border-light);
  border-radius: 8px; padding: 12px 14px; margin-bottom: 10px;
}
.form-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.form-row label { font-size: 12px; font-weight: 500; color: var(--text-muted); min-width: 48px; flex-shrink: 0; }
.form-row input[type="number"] { border: 1px solid var(--border); border-radius: 5px; padding: 5px 7px; font-size: 12px; outline: none; background: var(--surface); color: var(--text); width: 80px; }
.form-row input[type="time"] { border: 1px solid var(--border); border-radius: 5px; padding: 5px 7px; font-size: 12px; outline: none; background: var(--surface); color: var(--text); }
.form-row input:focus { border-color: var(--accent); }
.unit { font-size: 11px; color: var(--text-muted); }
.fixed-label { font-size: 12px; color: var(--text-muted); }
.tz-hint { font-size: 11px; color: var(--text-placeholder); margin-left: 6px; }
.range-input { width: 115px !important; }
.range-sep { font-size: 12px; color: var(--text-placeholder); }
.form-actions { display: flex; gap: 6px; margin-top: 4px; }

/* Rules list */
.rules-list { max-height: 240px; overflow-y: auto; }
.rule-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 7px 10px; border: 1px solid var(--border-light); border-radius: 6px;
  margin-bottom: 4px; font-size: 12px;
}
.rule-info { display: flex; align-items: center; gap: 8px; min-width: 0; }
.rule-tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 500; white-space: nowrap; flex-shrink: 0; }
.type-1 { background: #e0f2fe; color: #0369a1; }
.type-2 { background: #fef3c7; color: #92400e; }
.type-3 { background: #f3e8ff; color: #7c3aed; }
.type-4 { background: #dcfce7; color: #166534; }
.rule-summary { color: var(--text-muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rule-actions { display: flex; gap: 3px; flex-shrink: 0; margin-left: 8px; }

.empty-hint { text-align: center; color: var(--text-placeholder); font-size: 12px; padding: 16px 0; }
.detail-empty { padding: 60px 0 !important; }

/* 规则组管理响应式 */
.mobile-back-btn {
  display: none;
  border: none; background: none; padding: 4px 0; margin-bottom: 8px;
  font-size: 12px; cursor: pointer; color: var(--accent); font-weight: 500;
}

@media (max-width: 640px) {
  .layout { flex-direction: column; }
  .group-panel { width: 100% !important; }
  .group-panel.mobile-hidden { display: none; }
  .detail-panel { display: none; }
  .detail-panel.mobile-full { display: block; }
  .mobile-back-btn { display: block; }
  .detail-empty { padding: 40px 0 !important; }
}

.detail-loading { display: flex; align-items: center; justify-content: center; padding: 60px 0; }
.detail-loading .spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .6s linear infinite; }

.detail-inner { min-height: 260px; }
.detail-fade-enter-active { transition: opacity .12s ease; }
.detail-fade-leave-active { transition: opacity .08s ease; }
.detail-fade-enter-from, .detail-fade-leave-to { opacity: 0; }
.empty-videos { text-align: center; padding: 24px 0; color: var(--text-placeholder); font-size: 13px; }

/* Buttons */
.btn-sm {
  border: 1px solid var(--border); border-radius: 5px; padding: 3px 8px;
  font-size: 11px; cursor: pointer; font-weight: 500; transition: all .12s;
  background: var(--surface); color: var(--text-muted); margin-left: 3px;
}
.btn-sm:hover { background: var(--surface-hover); }
.btn-pause:hover { border-color: #f0c040; color: #b88a1e; background: #fef9e7; }
.btn-resume { border-color: #22c55e; color: #22c55e; background: #f0fdf4; }
.btn-resume:hover { background: #dcfce7; }
.btn-score-on { color: var(--accent); border-color: var(--accent-border); }
.btn-score-on:hover { background: var(--accent-light); }
.btn-score-off { color: var(--text-placeholder); border-color: var(--border-light); background: var(--surface-secondary); }
.btn-score-off:hover { color: var(--text-muted); border-color: var(--border); }
.btn-del { color: var(--text-placeholder); }
.btn-del:hover { color: var(--red); border-color: #fca5a5; background: #fef2f2; }

.btn-add {
  border: none; border-radius: 7px; padding: 7px 16px; font-size: 13px;
  cursor: pointer; background: var(--accent); color: #fff; font-weight: 500;
}
.btn-add:hover { background: var(--accent-hover); }
.btn-add-sm {
  border: 1px solid var(--accent); border-radius: 5px; padding: 4px 10px;
  font-size: 11px; cursor: pointer; font-weight: 500; background: var(--surface);
  color: var(--accent); transition: all .12s;
}
.btn-add-sm:hover { background: var(--accent-light); }

.btn-save {
  border: none; border-radius: 5px; padding: 5px 14px; font-size: 12px;
  cursor: pointer; font-weight: 500; background: var(--accent); color: #fff; transition: all .15s;
}
.btn-save:hover { background: var(--accent-hover); }
.btn-save:disabled { opacity: .6; }
.btn-save-sm {
  border: none; border-radius: 5px; padding: 5px 12px; font-size: 12px;
  cursor: pointer; font-weight: 500; background: var(--accent); color: #fff;
  flex-shrink: 0;
}
.btn-cancel {
  border: 1px solid var(--border); border-radius: 5px; padding: 5px 14px;
  font-size: 12px; cursor: pointer; background: var(--surface); color: var(--text-muted); transition: all .12s;
}
.btn-cancel:hover { background: var(--surface-hover); }
/* Log */
.log-section { margin-top: 4px; }
.log-box {
  background: var(--surface-secondary); border: 1px solid var(--border-light);
  border-radius: 8px; height: 140px; overflow-y: auto; padding: 10px 14px;
  font-family:
    "Cascadia Code", "SF Mono", "Fira Code", "Consolas", "Menlo",
    "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Hiragino Sans GB", "WenQuanYi Micro Hei",
    monospace;
  font-size: 13px; line-height: 1.7; color: var(--text-muted);
}
.log-empty { text-align: center; color: var(--text-placeholder); padding: 20px 0; }
.log-line { white-space: pre-wrap; word-break: break-all; }
.log-ok { color: var(--green); }
.log-err { color: var(--red); }

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
.btn-primary { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; background: var(--accent); color: #fff; transition: all .15s; }
.btn-primary:hover { background: var(--accent-hover); }

/* 管理页面中的UP主列表 */
.mgmt-uploader-groups { min-height: 100px; }
.mgmt-breadcrumb { margin-bottom: 8px; }
.mgmt-breadcrumb .back-btn {
  border: none; background: none; padding: 2px 8px; font-size: 12px;
  cursor: pointer; color: var(--accent); font-weight: 500; border-radius: 4px;
}
.mgmt-breadcrumb .back-btn:hover { background: var(--accent-light); }
.mgmt-up-list { max-height: 320px; overflow-y: auto; }
.mgmt-up-item {
  display: flex; align-items: center; gap: 10px; padding: 7px 10px;
  border-radius: 6px; cursor: pointer; transition: background .12s;
}
.mgmt-up-item:hover { background: var(--surface-hover); }
.mgmt-up-avatar { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; flex-shrink: 0; background: var(--surface-secondary); }
.mgmt-up-info { flex: 1; min-width: 0; }
.mgmt-up-name { font-size: 12px; font-weight: 500; }
.mgmt-up-count { font-size: 10px; color: var(--text-placeholder); display: block; }
.arrow { font-size: 16px; color: var(--text-placeholder); flex-shrink: 0; }

/* 管理页面搜索 */
.mgmt-search-wrap { position: relative; margin-bottom: 8px; }
.mgmt-search-input {
  width: 100%; border: 1px solid var(--border); border-radius: 7px;
  padding: 6px 28px 6px 10px; font-size: 12px; outline: none;
  background: var(--surface); color: var(--text);
  transition: border-color .2s; box-sizing: border-box;
}
.mgmt-search-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }
.mgmt-search-input::placeholder { color: var(--text-placeholder); }
.mgmt-search-wrap .search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  cursor: pointer; font-size: 13px; color: var(--text-placeholder); line-height: 1;
}
.mgmt-search-wrap .search-clear:hover { color: var(--text); }
.mgmt-search-results { max-height: 400px; overflow-y: auto; }
.search-up-header {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  background: var(--surface-secondary); border-radius: 6px; margin-bottom: 6px;
  cursor: pointer; transition: background .12s;
}
.search-up-header:hover { background: var(--surface-hover); }
.search-up-name { font-size: 12px; font-weight: 600; }
.search-up-count { font-size: 10px; color: var(--text-placeholder); }

/* Transitions */
.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
</style>
