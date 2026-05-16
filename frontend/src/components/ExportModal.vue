<script setup>
import { ref, inject, watch } from 'vue'
import DateTimePicker from './DateTimePicker.vue'

const props = defineProps({
  show: Boolean,
  videoId: Number,
  videoTitle: { type: String, default: '' },
})
const emit = defineEmits(['close'])
const api = inject('api')
const toastRef = inject('toast')

const now = new Date()
const endDefault = now.toISOString()
const startDefault = new Date(now.getTime() - 7 * 24 * 3600 * 1000).toISOString()

const startTime = ref('')
const endTime = ref('')
const exporting = ref(false)
const error = ref('')

watch(() => props.show, (v) => {
  if (v) {
    startTime.value = startDefault
    endTime.value = endDefault
    error.value = ''
    exporting.value = false
  }
})

function validate() {
  const s = new Date(startTime.value)
  const e = new Date(endTime.value)
  if (isNaN(s.getTime())) return '请选择开始时间'
  if (isNaN(e.getTime())) return '请选择结束时间'
  if (s >= e) return '开始时间必须早于结束时间'
  return null
}

async function doExport() {
  error.value = ''
  const err = validate()
  if (err) { error.value = err; return }

  exporting.value = true
  try {
    const tzOffset = -new Date().getTimezoneOffset()
    const { blob, filename } = await api.exportXlsx(props.videoId, startTime.value, endTime.value, tzOffset)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toastRef?.value?.show('导出成功', 'success')
    emit('close')
  } catch (e) {
    const msg = e?.response?.data?.error || e?.message || '导出失败'
    error.value = msg
    toastRef?.value?.show(msg, 'error')
  }
  exporting.value = false
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay">
        <div class="modal-box">
          <h2>导出数据</h2>

          <div v-if="videoTitle" class="video-name">{{ videoTitle }}</div>

          <section class="section">
            <h3>开始时间</h3>
            <DateTimePicker v-model="startTime" placeholder="选择开始时间" />
          </section>

          <section class="section">
            <h3>结束时间</h3>
            <DateTimePicker v-model="endTime" placeholder="选择结束时间" />
          </section>

          <p v-if="error" class="err">{{ error }}</p>

          <div class="actions">
            <button class="btn-cancel" @click="emit('close')">取消</button>
            <button class="btn-export" :disabled="exporting" @click="doExport">
              {{ exporting ? '导出中...' : '导出 XLSX' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 300;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 12vh;
  background: rgba(0,0,0,.35); backdrop-filter: blur(3px);
  overflow-y: auto;
}
.modal-box {
  background: #fff; border-radius: 14px; padding: 28px 32px;
  width: 440px; max-width: 94vw;
  box-shadow: 0 20px 60px rgba(0,0,0,.15); position: relative;
}
h2 { font-size: 17px; font-weight: 700; margin-bottom: 6px; }
.video-name {
  font-size: 12px; color: #888; margin-bottom: 16px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.section { margin-bottom: 18px; }
.section h3 { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 8px; }

.err { font-size: 12px; color: #ef4444; margin-top: 2px; }

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px; }
.btn-cancel {
  border: 1px solid #e0e0e0; border-radius: 7px; padding: 8px 20px;
  font-size: 13px; cursor: pointer; font-weight: 500; background: #fff;
  color: #666; transition: all .15s;
}
.btn-cancel:hover { background: #f5f6f8; }
.btn-export {
  border: none; border-radius: 7px; padding: 8px 20px;
  font-size: 13px; cursor: pointer; font-weight: 600;
  background: #4f8ef7; color: #fff; transition: all .15s;
}
.btn-export:hover { background: #3b7de6; }
.btn-export:disabled { opacity: .6; cursor: not-allowed; }

/* Transition */
.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
</style>
