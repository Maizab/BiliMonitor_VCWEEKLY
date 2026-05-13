<script setup>
import { ref } from 'vue'

const toasts = ref([])
let id = 0

function show(msg, type = '') {
  const item = { id: ++id, msg, type }
  toasts.value.push(item)
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== item.id)
  }, 3500)
}

defineExpose({ show })
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="(t, i) in toasts" :key="t.id"
          :class="['toast-item', t.type]"
          :style="{ top: i * 60 + 'px' }"
        >{{ t.msg }}</div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed; top: 16px; left: 50%; transform: translateX(-50%);
  z-index: 9999; pointer-events: none; width: 100%; max-width: 640px;
}
.toast-item {
  position: absolute; left: 0; right: 0;
  background: #333; color: #fff; padding: 14px 28px; border-radius: 10px;
  font-size: 15px; font-weight: 600; text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,.25); pointer-events: auto;
}
.toast-item.error { background: #ef4444; }
.toast-item.success { background: #22c55e; }

.toast-enter-active { transition: all .3s cubic-bezier(.22,.61,.36,1); }
.toast-leave-active { transition: all .2s ease-in; position: absolute; }
.toast-enter-from { opacity: 0; transform: translateY(-30px) scale(.95); }
.toast-leave-to { opacity: 0; transform: translateY(-16px) scale(.97); }
.toast-move { transition: transform .3s ease; }
</style>
