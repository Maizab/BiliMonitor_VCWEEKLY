<script setup>
import { ref, inject, watch } from 'vue'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['close'])
const api = inject('api')

const interval = ref(30)
const cookie = ref('')
const hasCookie = ref(false)
const saving = ref(false)
const saved = ref(false)
const loadingCfg = ref(false)

watch(() => props.show, async (v) => {
  if (v) {
    loadingCfg.value = true
    try {
      const cfg = await api.getConfig()
      interval.value = cfg.interval || 30
      hasCookie.value = cfg.has_cookie
    } catch (e) { /* ignore */ }
    cookie.value = ''
    saving.value = false
    saved.value = false
    loadingCfg.value = false
  }
})

async function save() {
  saving.value = true
  try {
    await api.saveConfig(interval.value, cookie.value.trim())
    saved.value = true
    if (cookie.value.trim() === 'clear') hasCookie.value = false
    else if (cookie.value.trim()) hasCookie.value = true
    setTimeout(() => {
      emit('close')
      cookie.value = ''
      saved.value = false
      saving.value = false
    }, 1200)
  } catch (e) {
    saving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay">
        <div class="modal-box">
          <h2>设置</h2>
          <div v-if="loadingCfg" class="cfg-spinner"><span class="spinner"></span></div>
          <template v-else>
          <label>采集间隔（秒）</label>
          <input type="number" v-model.number="interval" min="5" max="3600" />

          <label>Cookie <span class="optional">（选填）</span></label>
          <textarea v-model="cookie" placeholder="从浏览器复制完整 Cookie 字符串"></textarea>
          <p class="hint">Cookie 仅保存不返回，输入 <code>clear</code> 保存可清空已存储的 Cookie</p>

          <div v-if="hasCookie && !cookie.trim()" class="info ok">✓ 当前已填写 Cookie。如仍遇到风控校验失败，请尝试更新 Cookie</div>
          <div v-if="!hasCookie && !cookie.trim()" class="info warn">⚠ 当前未填写 Cookie，请求可能被B站风控拦截而不稳定</div>

          <span v-if="saved" class="saved-toast">✓ 已保存</span>
          </template>

          <div class="actions">
            <button class="btn-cancel" @click="emit('close')">取消</button>
            <button class="btn-primary" :disabled="saving" @click="save">
              {{ saving ? '保存中...' : saved ? '已保存' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 200;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,.35); backdrop-filter: blur(3px);
}
.modal-box {
  background: #fff; border-radius: 14px; padding: 28px 32px; width: 520px; max-width: 92vw;
  box-shadow: 0 20px 60px rgba(0,0,0,.15); position: relative; overflow: hidden;
}
h2 { font-size: 17px; font-weight: 700; margin-bottom: 20px; }
.cfg-spinner { display: flex; align-items: center; justify-content: center; padding: 40px 0; }
.cfg-spinner .spinner { width: 24px; height: 24px; border: 3px solid #e0e0e0; border-top-color: #4f8ef7; border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
label { display: block; font-size: 13px; font-weight: 500; color: #555; margin-bottom: 6px; margin-top: 14px; }
label:first-of-type { margin-top: 0; }
.optional { font-weight: 400; color: #aaa; }
input, textarea {
  width: 100%; border: 1px solid #e0e0e0; border-radius: 7px; padding: 8px 12px;
  font-size: 13px; outline: none; font-family: inherit; transition: border-color .2s;
}
input:focus, textarea:focus { border-color: #4f8ef7; box-shadow: 0 0 0 2px #4f8ef720; }
textarea { height: 100px; resize: vertical; }
.hint { font-size: 11px; color: #aaa; margin-top: 4px; }
.hint code { background: #f0f2f5; padding: 1px 5px; border-radius: 3px; }
.info { font-size: 12px; margin-top: 6px; padding: 8px 12px; border-radius: 6px; }
.info.warn { color: #b88a1e; background: #fef9e7; border-left: 3px solid #f0c040; }
.info.ok { color: #2e7d32; background: #e8f5e9; border-left: 3px solid #66bb6a; }
.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
.actions button { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; transition: all .15s; }
.btn-primary { background: #4f8ef7; color: #fff; }
.btn-primary:hover { background: #3b7de6; }
.btn-primary:disabled { opacity: .6; }
.btn-cancel { background: #f0f2f5; color: #555; }
.btn-cancel:hover { background: #e4e6ea; }
.saved-toast {
  position: absolute; top: 16px; right: 20px; background: #22c55e; color: #fff;
  padding: 6px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;
  pointer-events: none;
}

/* Transition */
.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
</style>
