<script setup>
import { ref, inject, watch, nextTick, computed } from 'vue'
import Dropdown from './Dropdown.vue'
import TimePicker from './TimePicker.vue'

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
const addingGroup = ref(false)

// Rename inline
const renamingGroupId = ref(null)
const renameText = ref('')

// Rule editor
const showRuleForm = ref(false)
const editingRule = ref(null)
const ruleType = ref(1)
const ruleInterval = ref(60)
const ruleCondMetric = ref('view_count')
const ruleCondMin = ref(null)
const ruleCondMax = ref(null)
const ruleCondInterval = ref(30)
const ruleTime = ref('03:00')
const ruleDow = ref(5)  // 0=Mon...6=Sun, default Saturday for Type 4

const RULE_TYPE_LABELS = { 1: '定长', 2: '条件精确', 3: '每天某点', 4: '每周定点' }
const WEEKDAY_NAMES = ['日', '一', '二', '三', '四', '五', '六']

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
    day_of_week: ((localDow - dayShift) % 7 + 7) % 7,
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
    cancelRuleEdit()
    newGroupName.value = ''; addingGroup.value = false
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
  try {
    await api.assignVideoRule(videoId, groupId)
    videos.value = await api.getVideos()
    toastRef?.value?.show('规则组已切换', 'success')
  } catch (e) { /* ignore */ }
}

function fmtTs(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Only for video table dropdown: map groups to {value, label}
const groupOptions = () => ruleGroups.value.map(g => ({ value: g.id, label: g.name }))

// ---- Rule group management ----
async function selectGroup(id) {
  selectedGroupId.value = id
  try {
    selectedGroup.value = await api.getRuleGroup(id)
  } catch (e) { selectedGroup.value = null }
  cancelRuleEdit()
}

async function doCreateGroup() {
  const name = newGroupName.value.trim()
  if (!name) return
  try {
    await api.createRuleGroup(name)
    newGroupName.value = ''
    addingGroup.value = false
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
  ruleGroups.value = await api.getRuleGroups()
  videos.value = await api.getVideos()
}

// ---- Rule editor ----
function startAddRule() {
  editingRule.value = null
  ruleType.value = 1
  ruleInterval.value = 60
  ruleCondMetric.value = 'view_count'
  ruleCondMin.value = null
  ruleCondMax.value = null
  ruleCondInterval.value = 30
  ruleTime.value = '03:00'
  ruleDow.value = 5
  showRuleForm.value = true
}

function startEditRule(rule) {
  editingRule.value = rule
  ruleType.value = rule.rule_type
  try {
    const v = typeof rule.value === 'string' ? JSON.parse(rule.value) : rule.value
    if (rule.rule_type === 1) {
      ruleInterval.value = v.interval || 60
    } else if (rule.rule_type === 2) {
      ruleCondMetric.value = v.metric || 'view_count'
      ruleCondMin.value = v.min_value ?? null
      ruleCondMax.value = v.max_value ?? null
      ruleCondInterval.value = v.target_interval || 30
    } else if (rule.rule_type === 3) {
      ruleTime.value = toLocalTime(v.time || '00:00')
    } else if (rule.rule_type === 4) {
      const l = toLocalDowTime(v.day_of_week ?? 4, v.time || '19:00')
      ruleDow.value = l.day_of_week
      ruleTime.value = l.time
    }
  } catch (e) {
    ruleInterval.value = 60
  }
  showRuleForm.value = true
}

function cancelRuleEdit() {
  showRuleForm.value = false
  editingRule.value = null
}

async function saveRule() {
  let value = {}
  if (ruleType.value === 1) {
    value = { interval: Math.max(30, ruleInterval.value) }
  } else if (ruleType.value === 2) {
    const minVal = ruleCondMin.value !== null && ruleCondMin.value !== '' ? Number(ruleCondMin.value) : null
    const maxVal = ruleCondMax.value !== null && ruleCondMax.value !== '' ? Number(ruleCondMax.value) : null
    value = {
      metric: ruleCondMetric.value,
      min_value: minVal,
      max_value: maxVal,
      target_interval: Math.max(30, ruleCondInterval.value),
    }
  } else if (ruleType.value === 3) {
    value = { time: toUtcTime(ruleTime.value) }
  } else if (ruleType.value === 4) {
    const u = toUtcDowTime(ruleDow.value, ruleTime.value)
    value = { day_of_week: u.day_of_week, time: u.time }
  }

  try {
    if (editingRule.value) {
      await api.updateRule(editingRule.value.id, ruleType.value, value)
    } else {
      await api.addRule(selectedGroupId.value, ruleType.value, value)
    }
    selectedGroup.value = await api.getRuleGroup(selectedGroupId.value)
    await refreshGroups()
    cancelRuleEdit()
    emit('change')
    toastRef?.value?.show('规则已保存', 'success')
  } catch (e) { /* ignore */ }
}

async function deleteRuleById(ruleId) {
  if (!confirmRef?.value) return
  const ok = await confirmRef.value.open('确认删除该规则？', '确认删除')
  if (!ok) return
  try {
    await api.deleteRule(ruleId)
    selectedGroup.value = await api.getRuleGroup(selectedGroupId.value)
    await refreshGroups()
    emit('change')
    toastRef?.value?.show('规则已删除', 'success')
  } catch (e) { /* ignore */ }
}

function ruleSummary(rule) {
  try {
    const v = typeof rule.value === 'string' ? JSON.parse(rule.value) : rule.value
    if (rule.rule_type === 1) return `每 ${v.interval}s`
    if (rule.rule_type === 2) {
      const parts = []
      if (v.min_value != null) parts.push(`≥ ${v.min_value}`)
      if (v.max_value != null) parts.push(`≤ ${v.max_value}`)
      parts.push(`→ ${v.target_interval}s`)
      return `${v.metric} ${parts.join(' ')}`
    }
    if (rule.rule_type === 3) return `每天 ${toLocalTime(v.time)} (${tzLabel})`
    if (rule.rule_type === 4) {
      const l = toLocalDowTime(v.day_of_week ?? 4, v.time || '19:00')
      return `每周${WEEKDAY_NAMES[l.day_of_week]} ${l.time}`
    }
  } catch (e) { return '-' }
  return '-'
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
                  <div class="video-table-wrap">
                    <table v-if="videos.length" class="video-table">
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
                        <tr v-for="v in videos" :key="v.id" :class="{ paused: v.paused }">
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
                    <div v-else class="empty-videos">暂无视频，添加一个开始监控</div>
                  </div>
                </section>
              </template>

              <!-- ========== Tab: 规则组管理 ========== -->
              <template v-if="activeTab === 'rules'">
                <div class="layout">
                  <!-- 左侧：规则组列表 -->
                  <div class="group-panel">
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
                          <button class="btn-icon" title="重命名" @click="startRename(g)">✎</button>
                          <button class="btn-icon btn-danger" title="删除"
                            :disabled="isDefaultGroup(g)" @click="deleteGroup(g)">✕</button>
                        </div>
                      </div>
                      <div v-if="!ruleGroups.length" class="empty-hint">暂无规则组</div>
                    </div>
                    <!-- 新建组 -->
                    <div class="panel-footer">
                      <template v-if="addingGroup">
                        <input class="new-group-input" v-model="newGroupName" placeholder="组名称"
                          @keydown.enter="doCreateGroup" @keydown.escape="addingGroup = false" autofocus />
                        <button class="btn-save-sm" @click="doCreateGroup">确定</button>
                        <button class="btn-cancel-sm" @click="addingGroup = false; newGroupName = ''">取消</button>
                      </template>
                      <button v-else class="btn-add-block" @click="addingGroup = true">+ 新建规则组</button>
                    </div>
                  </div>

                  <!-- 右侧：组详情 -->
                  <div class="detail-panel">
                    <template v-if="selectedGroup">
                      <div class="detail-header">
                        <h3>{{ selectedGroup.name }} — 规则列表</h3>
                        <button v-if="!showRuleForm" class="btn-add-sm" @click="startAddRule">+ 添加规则</button>
                      </div>

                      <!-- 规则编辑表单 -->
                      <div v-if="showRuleForm" class="rule-form">
                        <div class="form-row">
                          <label>类型</label>
                          <Dropdown :options="RULE_TYPE_OPTIONS" v-model="ruleType" />
                        </div>

                        <!-- Type 1 -->
                        <div v-if="ruleType === 1" class="form-row">
                          <label>间隔</label>
                          <input type="number" v-model.number="ruleInterval" min="30" />
                          <span class="unit">秒</span>
                        </div>

                        <!-- Type 2: 条件精确 -->
                        <template v-if="ruleType === 2">
                          <div class="form-row">
                            <label>指标</label>
                            <Dropdown :options="METRIC_OPTIONS" v-model="ruleCondMetric" />
                          </div>
                          <div class="form-row">
                            <label>区间</label>
                            <input type="number" v-model.number="ruleCondMin" placeholder="最小值（可选）" class="range-input" />
                            <span class="range-sep">~</span>
                            <input type="number" v-model.number="ruleCondMax" placeholder="最大值（可选）" class="range-input" />
                          </div>
                          <div class="form-row">
                            <label>步长</label>
                            <input type="number" v-model.number="ruleCondInterval" min="30" />
                            <span class="unit">秒（条件成立时）</span>
                          </div>
                        </template>

                        <!-- Type 3 / 4 -->
                        <div v-if="ruleType === 3" class="form-row">
                          <label>时间</label>
                          <TimePicker v-model="ruleTime" />
                          <span class="tz-hint">{{ tzLabel }}</span>
                        </div>
                        <div v-if="ruleType === 4" class="form-row">
                          <label>时间</label>
                          <Dropdown :options="DOW_OPTIONS" v-model="ruleDow" style="min-width:70px" />
                          <TimePicker v-model="ruleTime" />
                          <span class="tz-hint">{{ tzLabel }}</span>
                        </div>

                        <div class="form-actions">
                          <button class="btn-save" @click="saveRule">{{ editingRule ? '更新' : '添加' }}</button>
                          <button class="btn-cancel" @click="cancelRuleEdit">取消</button>
                        </div>
                      </div>

                      <!-- 规则列表 -->
                      <div class="rules-list">
                        <div v-if="!selectedGroup.rules?.length" class="empty-hint">暂无规则，添加一条开始</div>
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
                    </template>
                    <div v-else class="empty-hint detail-empty">← 选择一个规则组查看详情</div>
                  </div>
                </div>
              </template>
            </template>
          </template>

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
.video-table th { position: sticky; top: 0; background: var(--surface-secondary); padding: 8px 10px; text-align: left; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-light); white-space: nowrap; }
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
.panel-footer { padding: 6px; border-top: 1px solid var(--border-light); }

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

.new-group-input { width: calc(100% - 80px); border: 1px solid var(--accent); border-radius: 4px; padding: 5px 8px; font-size: 12px; outline: none; margin-right: 4px; }

.btn-icon {
  border: none; background: none; cursor: pointer; font-size: 12px;
  padding: 2px 4px; border-radius: 3px; color: var(--text-muted); transition: all .12s;
}
.btn-icon:hover { background: var(--surface-hover); color: var(--text); }
.btn-icon:disabled { opacity: .3; cursor: not-allowed; }
.btn-icon.btn-danger:hover { color: var(--red); background: #fef2f2; }

.btn-add-block {
  width: 100%; border: 1px dashed var(--border); border-radius: 6px; padding: 6px;
  font-size: 12px; cursor: pointer; background: none; color: var(--accent);
  transition: all .12s;
}
.btn-add-block:hover { border-color: var(--accent); background: var(--accent-light); }

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
  border: none; border-radius: 4px; padding: 4px 10px; font-size: 11px;
  cursor: pointer; font-weight: 500; background: var(--accent); color: #fff;
}
.btn-cancel {
  border: 1px solid var(--border); border-radius: 5px; padding: 5px 14px;
  font-size: 12px; cursor: pointer; background: var(--surface); color: var(--text-muted); transition: all .12s;
}
.btn-cancel:hover { background: var(--surface-hover); }
.btn-cancel-sm {
  border: 1px solid var(--border); border-radius: 4px; padding: 4px 10px; font-size: 11px;
  cursor: pointer; background: var(--surface); color: var(--text-muted);
}

/* Log */
.log-section { margin-top: 4px; }
.log-box {
  background: var(--surface-secondary); border: 1px solid var(--border-light);
  border-radius: 8px; height: 140px; overflow-y: auto; padding: 10px 14px;
  font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
  font-size: 12px; line-height: 1.7; color: var(--text-muted);
}
.log-empty { text-align: center; color: var(--text-placeholder); padding: 20px 0; }
.log-line { white-space: pre-wrap; word-break: break-all; }
.log-ok { color: var(--green); }
.log-err { color: var(--red); }

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
.btn-primary { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; background: var(--accent); color: #fff; transition: all .15s; }
.btn-primary:hover { background: var(--accent-hover); }

/* Transitions */
.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
</style>
