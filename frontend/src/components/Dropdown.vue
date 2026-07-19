<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  options: { type: Array, default: () => [] },
  modelValue: { default: null },
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const root = ref(null)

function select(opt) {
  emit('update:modelValue', opt.value)
  open.value = false
}

function onMouseDown(e) {
  if (root.value && !root.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', onMouseDown))
onBeforeUnmount(() => document.removeEventListener('mousedown', onMouseDown))

const selectedLabel = () => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt ? opt.label : props.placeholder
}
</script>

<template>
  <div class="dd-root" ref="root" :class="{ disabled }">
    <div class="dd-trigger" @click="!disabled && (open = !open)">
      <span :class="['dd-label', { placeholder: !options.find(o => o.value === modelValue) }]">
        {{ selectedLabel() }}
      </span>
      <span class="dd-arrow">▾</span>
    </div>
    <Transition name="dd">
      <div v-if="open" class="dd-menu">
        <div
          v-for="opt in options" :key="opt.value"
          :class="['dd-item', { active: opt.value === modelValue }]"
          @click="select(opt)"
        >{{ opt.label }}</div>
        <div v-if="!options.length" class="dd-empty">无选项</div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dd-root { position: relative; user-select: none; min-width: 0; }
.dd-root.disabled { opacity: .45; pointer-events: none; }

.dd-trigger {
  display: flex; align-items: center; justify-content: space-between; gap: 4px;
  border: 1px solid var(--border); border-radius: 6px;
  padding: 6px 8px; font-size: 12px; cursor: pointer;
  background: var(--surface); color: var(--text);
  transition: border-color .15s; white-space: nowrap;
}
.dd-trigger:hover { border-color: var(--accent); }
.dd-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.dd-label.placeholder { color: var(--text-placeholder); }
.dd-arrow { font-size: 10px; color: var(--text-muted); flex-shrink: 0; transition: transform .15s; }

.dd-menu {
  position: absolute; top: calc(100% + 4px); left: 0;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 7px; box-shadow: var(--shadow-lg); z-index: 300;
  max-height: 220px; overflow-y: auto; overflow-x: hidden;
  min-width: max-content; padding: 4px;
}
.dd-item {
  padding: 6px 10px; font-size: 12px; border-radius: 4px;
  cursor: pointer; color: var(--text); transition: background .1s;
  white-space: nowrap;
}
.dd-item:hover { background: var(--surface-hover); }
.dd-item.active { background: var(--accent-light); color: var(--accent); font-weight: 500; }
.dd-empty { padding: 8px 10px; font-size: 12px; color: var(--text-placeholder); text-align: center; }

.dd-enter-active { transition: opacity .12s, transform .12s; }
.dd-leave-active { transition: opacity .1s, transform .1s; }
.dd-enter-from, .dd-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
