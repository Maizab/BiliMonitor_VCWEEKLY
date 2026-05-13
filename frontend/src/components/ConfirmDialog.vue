<script setup>
import { ref } from 'vue'

const show = ref(false)
const msg = ref('')
let resolveFn = null

function open(text) {
  msg.value = text
  show.value = true
  return new Promise(resolve => { resolveFn = resolve })
}

function confirm() { show.value = false; resolveFn?.(true) }
function cancel() { show.value = false; resolveFn?.(false) }

defineExpose({ open })
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay" @click.self="cancel">
        <div class="modal-box">
          <p>{{ msg }}</p>
          <div class="actions">
            <button class="btn-cancel" @click="cancel">取消</button>
            <button class="btn-primary" @click="confirm">确认删除</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 210;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,.35); backdrop-filter: blur(3px);
}
.modal-box {
  background: #fff; border-radius: 14px; padding: 28px 32px; width: 380px;
  max-width: 92vw; box-shadow: 0 20px 60px rgba(0,0,0,.15); text-align: center;
}
p { font-size: 14px; color: #333; margin-bottom: 18px; }
.actions { display: flex; gap: 10px; justify-content: center; }
.actions button { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; transition: all .15s; }
.btn-primary { background: #4f8ef7; color: #fff; }
.btn-primary:hover { background: #3b7de6; }
.btn-cancel { background: #f0f2f5; color: #555; }
.btn-cancel:hover { background: #e4e6ea; }

.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92); }
</style>
