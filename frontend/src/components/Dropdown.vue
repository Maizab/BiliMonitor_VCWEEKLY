<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'

const props = defineProps({
  options: { type: Array, default: () => [] },
  modelValue: { default: null },
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const root = ref(null)
const menuStyle = ref({})

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

function calcPos() {
  if (!root.value) return
  const rect = root.value.querySelector('.dd-trigger').getBoundingClientRect()
  menuStyle.value = {
    position: 'fixed',
    top: (rect.bottom + 4) + 'px',
    left: rect.left + 'px',
    minWidth: rect.width + 'px',
  }
}

watch(open, async (v) => {
  if (v) {
    await nextTick()
    calcPos()
  }
})
</script>

<template>
  <div class="dd-root" ref="root" :class="{ disabled }">
    <div class="dd-trigger" @click="!disabled && (open = !open)">
      <span :class="['dd-label', { placeholder: !options.find(o => o.value === modelValue) }]">
        {{ selectedLabel() }}
      </span>
      <span class="dd-arrow">▾</span>
    </div>
    <Teleport to="body">
      <Transition name="dd">
        <div v-if="open" class="dd-menu" :style="menuStyle">
          <div
            v-for="opt in options" :key="opt.value"
            :class="['dd-item', { active: opt.value === modelValue }]"
            @click.stop="select(opt)"
          >{{ opt.label }}</div>
          <div v-if="!options.length" class="dd-empty">无选项</div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style>
.dd-menu {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 7px; box-shadow: var(--shadow-lg); z-index: 9999;
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
</style>
