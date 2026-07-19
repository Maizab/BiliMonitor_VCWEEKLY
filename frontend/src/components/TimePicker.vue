<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '00:00' },  // "HH:MM" in UTC+8
})
const emit = defineEmits(['update:modelValue'])

function parse(s) {
  if (!s) return [0, 0]
  const parts = s.split(':')
  const h = Math.max(0, Math.min(23, parseInt(parts[0]) || 0))
  const m = Math.max(0, Math.min(59, parseInt(parts[1]) || 0))
  return [h, m]
}

const hour = ref(0)
const min = ref(0)

watch(() => props.modelValue, (v) => {
  const [h, m] = parse(v)
  hour.value = h; min.value = m
}, { immediate: true })

function emitVal(h, m) {
  const v = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  emit('update:modelValue', v)
}

// Stepper
function stepHour(dir) {
  let h = hour.value + dir
  if (h < 0) h = 23
  if (h > 23) h = 0
  emitVal(h, min.value)
}

function stepMin(dir) {
  let m = min.value + dir * 5
  if (m < 0) m = 55
  if (m > 55) m = 0
  emitVal(hour.value, m)
}

// Inline edit
const editHour = ref(false)
const editMin = ref(false)
const editHourVal = ref('')
const editMinVal = ref('')
const hourInputEl = ref(null)
const minInputEl = ref(null)

function startEditHour() {
  editHour.value = true
  editHourVal.value = String(hour.value).padStart(2, '0')
  nextTick(() => hourInputEl.value?.focus())
}
function startEditMin() {
  editMin.value = true
  editMinVal.value = String(min.value).padStart(2, '0')
  nextTick(() => minInputEl.value?.focus())
}

function onHourInput(e) {
  let v = e.target.value.replace(/\D/g, '')
  if (v.length > 2) v = v.slice(0, 2)
  editHourVal.value = v
}
function onMinInput(e) {
  let v = e.target.value.replace(/\D/g, '')
  if (v.length > 2) v = v.slice(0, 2)
  editMinVal.value = v
}

function commitHour() {
  editHour.value = false
  let v = parseInt(editHourVal.value, 10)
  if (isNaN(v) || v < 0) v = 0
  if (v > 23) v = 23
  emitVal(v, min.value)
}
function commitMin() {
  editMin.value = false
  let v = parseInt(editMinVal.value, 10)
  if (isNaN(v) || v < 0) v = 0
  if (v > 59) v = 59
  emitVal(hour.value, v)
}

function onHourKey(e) {
  if (e.key === 'Enter') commitHour()
  if (e.key === 'Escape') { editHour.value = false }
}
function onMinKey(e) {
  if (e.key === 'Enter') commitMin()
  if (e.key === 'Escape') { editMin.value = false }
}
</script>

<template>
  <div class="tp-stepper">
    <!-- Hours -->
    <div class="tp-col">
      <button class="tp-btn" @click="stepHour(1)">▲</button>
      <div class="tp-val" @click="startEditHour" v-if="!editHour">
        {{ String(hour).padStart(2, '0') }}
      </div>
      <input
        v-else
        ref="hourInputEl"
        class="tp-input"
        :value="editHourVal"
        @input="onHourInput"
        @blur="commitHour"
        @keydown="onHourKey"
      />
      <button class="tp-btn" @click="stepHour(-1)">▼</button>
    </div>
    <span class="tp-colon">:</span>
    <!-- Minutes -->
    <div class="tp-col">
      <button class="tp-btn" @click="stepMin(1)">▲</button>
      <div class="tp-val" @click="startEditMin" v-if="!editMin">
        {{ String(min).padStart(2, '0') }}
      </div>
      <input
        v-else
        ref="minInputEl"
        class="tp-input"
        :value="editMinVal"
        @input="onMinInput"
        @blur="commitMin"
        @keydown="onMinKey"
      />
      <button class="tp-btn" @click="stepMin(-1)">▼</button>
    </div>
  </div>
</template>

<style scoped>
.tp-stepper {
  display: flex; align-items: center; gap: 8px;
  font-variant-numeric: tabular-nums;
}
.tp-colon {
  font-size: 22px; font-weight: 600; color: var(--text-placeholder); padding-bottom: 4px;
}
.tp-col {
  display: flex; flex-direction: column; align-items: center; gap: 1px;
}
.tp-btn {
  width: 50px; height: 24px; border: 1px solid var(--border); background: var(--surface-secondary);
  border-radius: 5px; cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: var(--text-muted); transition: all .12s; user-select: none;
  padding: 0; line-height: 1;
}
.tp-btn:hover { background: var(--accent-light); border-color: var(--accent); color: var(--accent); }

.tp-val {
  width: 50px; height: 40px; display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 700; color: var(--text);
  background: var(--surface-secondary); border: 1.5px solid transparent; border-radius: 6px;
  cursor: pointer; transition: all .12s; user-select: none;
}
.tp-val:hover { border-color: var(--accent); background: var(--surface); }

.tp-input {
  width: 50px; height: 40px; text-align: center;
  font-size: 22px; font-weight: 700; color: var(--text);
  background: var(--surface); border: 1.5px solid var(--accent); border-radius: 6px;
  outline: none; font-family: inherit; font-variant-numeric: tabular-nums;
  box-shadow: 0 0 0 3px rgba(79,142,247,0.12);
}
.tp-input:focus { border-color: var(--accent); }
</style>
