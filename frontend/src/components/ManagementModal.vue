<script setup>
import { ref, inject, watch, nextTick } from 'vue'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['close', 'change'])
const api = inject('api')
const confirmRef = inject('confirm')
const toastRef = inject('toast')
const logLines = inject('logLines', ref([]))

const interval = ref(30)
const saving = ref(false)
const saved = ref(false)
const loading = ref(false)
const loadedOnce = ref(false)

const logBox = ref(null)
const logAutoScroll = ref(true)
const logReady = ref(false)

// Auth state
const authReady = ref(false)
const authPassword = ref('')
const authError = ref('')
const authChecking = ref(false)

// Video management
const videos = inject('videos')
const newBvid = ref('')

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

async function loadCfg() {
  if (!loadedOnce.value) loading.value = true
  try {
    const cfg = await api.getConfig()
    interval.value = cfg.interval || 30
    videos.value = await api.getVideos()
  } catch (e) { /* ignore */ }
  loading.value = false
  loadedOnce.value = true
}

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
    saving.value = false
    saved.value = false
    authPassword.value = ''
    authError.value = ''

    const cached = sessionStorage.getItem('auth-password')
    if (cached) {
      // 验证缓存的密码是否仍然有效
      authChecking.value = true
      try {
        await api.verifyPassword(cached)
        authReady.value = true
      } catch (e) {
        // 密码已失效，清空缓存
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
      } catch (e) {
        authReady.value = true
      }
    }
    // 日志滚底 — 先隐藏，滚完再显示，消除闪烁
    logReady.value = false
    nextTick(() => {
      if (logBox.value) {
        logBox.value.scrollTop = logBox.value.scrollHeight
        logReady.value = true
      }
    })

    if (authReady.value) {
      await loadCfg()
    }
  }
})

async function saveInterval() {
  saving.value = true
  try {
    await api.saveConfig(interval.value)
    saved.value = true
    setTimeout(() => { saved.value = false; saving.value = false }, 1000)
  } catch (e) { saving.value = false }
}

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
  } catch (e) { /* toast handled by interceptor */ }
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
  } catch (e) {
    v.score_enabled = !v.score_enabled
  }
  emit('change')
}

function fmtTs(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = n => String(n).padStart(2,'0')
  return `${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay">
        <div class="modal-box">
          <h2>管理</h2>

          <!-- Password prompt -->
          <div v-if="!authReady" class="auth-box">
            <p class="auth-label">请输入密码以使用完整管理功能</p>
            <form class="auth-row" @submit.prevent="doVerify">
              <input
                type="password"
                v-model="authPassword"
                placeholder="密码"
                :disabled="authChecking"
              />
              <button class="btn-save" type="submit" :disabled="authChecking">
                {{ authChecking ? '验证中...' : '确认' }}
              </button>
            </form>
            <p v-if="authError" class="auth-error">{{ authError }}</p>
          </div>

          <template v-else>
            <div v-if="loading" class="cfg-spinner"><span class="spinner"></span></div>
            <template v-else>
              <!-- Interval -->
              <section class="section">
                <h3>采集间隔</h3>
                <div class="interval-row">
                  <input type="number" v-model.number="interval" min="30" max="3600" />
                  <span class="unit">秒</span>
                  <button class="btn-save" :disabled="saving" @click="saveInterval">
                    {{ saved ? '已保存' : '保存' }}
                  </button>
                </div>
              </section>

              <!-- Video management -->
              <section class="section">
                <h3>监控视频 <span class="count">({{ videos.length }})</span></h3>
                <div class="add-row">
                  <input type="text" v-model="newBvid" placeholder="输入 BV 号添加"
                    @keydown.enter="addVideo" />
                  <button class="btn-add" @click="addVideo">添加</button>
                </div>
                <div class="video-table-wrap">
                  <table v-if="videos.length" class="video-table">
                    <thead>
                      <tr>
                        <th class="col-title">视频</th>
                        <th class="col-count">已记录数据条数</th>
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
                        <td class="col-count">{{ v.snapshot_count || 0 }}</td>
                        <td class="col-time">{{ fmtTs(v.last_snapshot_at) }}</td>
                        <td class="col-actions">
                          <button
                            :class="['btn-sm', v.paused ? 'btn-resume' : 'btn-pause']"
                            :title="v.paused ? '继续采集' : '暂停采集'"
                            @click="togglePaused(v)"
                          >{{ v.paused ? '继续' : '暂停' }}</button>
                          <button
                            :class="['btn-sm', v.score_enabled ? 'btn-score-on' : 'btn-score-off']"
                            :title="v.score_enabled ? '关闭得点' : '得点已关闭'"
                            @click="toggleScore(v)"
                          >{{ v.score_enabled ? '得点' : '得点' }}</button>
                          <button class="btn-sm btn-del" @click="deleteVideo(v.id)" title="删除">删除</button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="empty-videos">暂无视频，添加一个开始监控</div>
                </div>
              </section>
            </template>
          </template>

          <!-- 日志查看器（无需密码） -->
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
  padding-top: 10vh;
  background: var(--overlay); backdrop-filter: blur(3px);
  overflow-y: auto;
}
.modal-box {
  background: var(--surface); border-radius: 14px; padding: 28px 32px;
  width: 680px; max-width: 94vw;
  box-shadow: var(--shadow-lg); position: relative;
}
h2 { font-size: 17px; font-weight: 700; margin-bottom: 20px; }

.auth-box { padding: 10px 0 24px; }
.auth-label { font-size: 13px; color: var(--text-secondary); margin-bottom: 10px; }
.auth-row { display: flex; gap: 8px; align-items: center; }
.auth-row input { flex: 1; border: 1px solid var(--border); border-radius: 7px; padding: 7px 11px; font-size: 13px; outline: none; background: var(--surface); color: var(--text); transition: border-color .2s; }
.auth-row input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }
.auth-error { font-size: 12px; color: var(--red); margin-top: 8px; }

.cfg-spinner { display: flex; align-items: center; justify-content: center; padding: 40px 0; }
.cfg-spinner .spinner { width: 24px; height: 24px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.section { margin-bottom: 22px; }
.section h3 { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 10px; }
.count { font-weight: 400; color: var(--text-placeholder); }

.interval-row { display: flex; align-items: center; gap: 8px; }
.interval-row input { width: 100px; border: 1px solid var(--border); border-radius: 7px; padding: 7px 11px; font-size: 13px; outline: none; background: var(--surface); color: var(--text); transition: border-color .2s; }
.interval-row input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }
.unit { font-size: 13px; color: var(--text-muted); }

.btn-save {
  border: none; border-radius: 7px; padding: 7px 16px; font-size: 12px;
  cursor: pointer; font-weight: 500; background: var(--accent); color: #fff; transition: all .15s;
}
.btn-save:hover { background: var(--accent-hover); }
.btn-save:disabled { opacity: .6; }

.add-row { display: flex; gap: 8px; margin-bottom: 10px; }
.add-row input { flex: 1; border: 1px solid var(--border); border-radius: 7px; padding: 7px 11px; font-size: 13px; outline: none; background: var(--surface); color: var(--text); transition: border-color .2s; }
.add-row input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px #4f8ef720; }
.btn-add { border: none; border-radius: 7px; padding: 7px 16px; font-size: 13px; cursor: pointer; background: var(--accent); color: #fff; font-weight: 500; }
.btn-add:hover { background: var(--accent-hover); }

.video-table-wrap { max-height: 340px; overflow-y: auto; border: 1px solid var(--border-light); border-radius: 8px; }
.video-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.video-table th { position: sticky; top: 0; background: var(--surface-secondary); padding: 8px 10px; text-align: left; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-light); white-space: nowrap; }
.video-table td { padding: 8px 10px; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
.video-table tbody tr:hover { background: var(--surface-hover); }
.video-table tbody tr.paused { opacity: .55; }
.video-table tbody tr.paused:hover { opacity: .75; }

.col-title { min-width: 160px; }
.col-count { width: 50px; text-align: center; color: var(--text-muted); }
.col-time { width: 120px; white-space: nowrap; color: var(--text-muted); }
.col-actions { width: 140px; white-space: nowrap; text-align: right; }

.v-title { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 240px; }
.v-bvid { font-size: 11px; color: var(--text-placeholder); }

.btn-sm {
  border: 1px solid var(--border); border-radius: 5px; padding: 3px 8px;
  font-size: 11px; cursor: pointer; font-weight: 500; transition: all .12s;
  background: var(--surface); color: var(--text-muted); margin-left: 4px;
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

.empty-videos { text-align: center; padding: 28px 0; color: var(--text-placeholder); font-size: 13px; }

/* 日志查看器 */
.log-section { margin-top: 6px; }
.log-box {
  background: var(--surface-secondary); border: 1px solid var(--border-light);
  border-radius: 8px; height: 180px; overflow-y: auto; padding: 10px 14px;
  font-family: "SF Mono", "Cascadia Code", "Consolas", monospace;
  font-size: 12px; line-height: 1.7; color: var(--text-muted);
}
.log-empty { text-align: center; color: var(--text-placeholder); padding: 20px 0; }
.log-line { white-space: pre-wrap; word-break: break-all; }
.log-ok { color: var(--green); }
.log-err { color: var(--red); }

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 4px; }
.btn-primary { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; background: var(--accent); color: #fff; transition: all .15s; }
.btn-primary:hover { background: var(--accent-hover); }

/* Transition */
.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
</style>
