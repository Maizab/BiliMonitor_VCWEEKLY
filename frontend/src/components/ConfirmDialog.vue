<script setup>
import { ref } from 'vue'

const show = ref(false)
const msg = ref('')
const btnText = ref('确认删除')
let resolveFn = null

function open(text, confirmText = '确认删除') {
  msg.value = text
  btnText.value = confirmText
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
            <button class="btn-primary" @click="confirm">{{ btnText }}</button>
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
  background: var(--overlay); backdrop-filter: blur(3px);
}
.modal-box {
  background: var(--surface); border-radius: 14px; padding: 28px 32px; width: 380px;
  max-width: 92vw; box-shadow: var(--shadow-lg); text-align: center;
}
p { font-size: 14px; color: var(--text); margin-bottom: 18px; }
.actions { display: flex; gap: 10px; justify-content: center; }
.actions button { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; transition: all .15s; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-cancel { background: var(--bg); color: var(--text-secondary); }
.btn-cancel:hover { background: var(--border); }

.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92); }
</style>
