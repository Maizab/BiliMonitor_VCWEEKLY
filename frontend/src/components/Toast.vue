<script setup>
import { ref } from 'vue'

const toasts = ref([])
let id = 0

function show(msg, type = 'info') {
  const item = { id: ++id, msg, type }
  toasts.value.push(item)
  setTimeout(() => dismiss(item), 3000)
}

function dismiss(item) {
  toasts.value = toasts.value.filter(x => x.id !== item.id)
}

defineExpose({ show })
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts" :key="t.id"
          :class="['toast-item', `toast-${t.type || 'info'}`]"
        >
          <!-- success icon -->
          <svg v-if="t.type === 'success'" class="toast-icon" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" fill="#d1e7dd" stroke="#0f5132" stroke-width="1.5"/>
            <path d="M7 12.5l3 3 7-7" stroke="#0f5132" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <!-- error icon -->
          <svg v-else-if="t.type === 'error'" class="toast-icon" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" fill="#f8d7da" stroke="#842029" stroke-width="1.5"/>
            <path d="M8 8l8 8M16 8l-8 8" stroke="#842029" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <!-- info / default icon -->
          <svg v-else class="toast-icon" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" fill="#cff4fc" stroke="#055160" stroke-width="1.5"/>
            <path d="M12 11v5M12 7v1" stroke="#055160" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span class="toast-msg">{{ t.msg }}</span>
          <button class="toast-close" @click="dismiss(t)">
            <svg viewBox="0 0 24 24" fill="none" class="close-icon">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed; top: 16px; right: 16px; z-index: 1060;
  pointer-events: none; max-width: 420px;
}

.toast-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 16px 20px; border-radius: 0.75rem;
  font-size: 14px; line-height: 1.5;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  pointer-events: auto; min-width: 340px;
  margin-bottom: 12px;
}

.toast-info     { background: #cff4fc; color: #055160; }
.toast-success  { background: #d1e7dd; color: #0f5132; }
.toast-error    { background: #f8d7da; color: #842029; }

.toast-icon { width: 24px; height: 24px; flex-shrink: 0; margin-top: 1px; }

.toast-msg { flex: 1; font-weight: 500; }

.toast-close {
  flex-shrink: 0; border: none; background: none; cursor: pointer;
  padding: 0; line-height: 1; opacity: .45; transition: opacity .12s;
  color: inherit;
}
.toast-close:hover { opacity: .75; }
.close-icon { width: 16px; height: 16px; }

/* TransitionGroup */
.toast-enter-active { transition: all .25s ease-out; }
.toast-leave-active {
  transition: all .25s ease-in;
  position: absolute; right: 0;
}
.toast-move       { transition: all .25s ease; }
.toast-enter-from { opacity: 0; transform: translateX(80px); }
.toast-leave-to   { opacity: 0; transform: translateX(100%); }
.toast-move       { transition: all .3s ease; }
</style>
