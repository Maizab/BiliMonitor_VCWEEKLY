<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

const MONTHS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
const WEEKDAYS = ['日','一','二','三','四','五','六']
const ACCENT = '#4f8ef7'
const ACCENT_LIGHT = '#eff3ff'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '选择日期时间' },
})
const emit = defineEmits(['update:modelValue'])

function fmt(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function fmtTime(h, m) {
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`
}

function parseValue(s) {
  if (!s) return null
  // 解析 ISO 8601 UTC 字符串（如 "2026-05-16T06:30:00.000Z"）
  const d = new Date(s)
  return isNaN(d.getTime()) ? null : d
}

const now = new Date()
const todayStr = fmt(now)
const nowHour = now.getHours()
const nowMin = now.getMinutes()

const open = ref(false)
const closing = ref(false)
const viewMode = ref('days')
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth())
const yearRange = ref(Math.floor(now.getFullYear() / 12) * 12)
const wrapperRef = ref(null)

const selectedDate = computed(() => parseValue(props.modelValue))
const selectedHour = computed(() => selectedDate.value ? selectedDate.value.getHours() : 0)
const selectedMin = computed(() => selectedDate.value ? selectedDate.value.getMinutes() : 0)

const displayText = computed(() => {
  const d = selectedDate.value
  if (!d) return props.placeholder
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日 周${WEEKDAYS[d.getDay()]} ${fmtTime(d.getHours(), d.getMinutes())}`
})

function syncToSelected() {
  const ref = selectedDate.value || now
  viewYear.value = ref.getFullYear()
  viewMonth.value = ref.getMonth()
  yearRange.value = Math.floor(ref.getFullYear() / 12) * 12
  viewMode.value = 'days'
}

function handleClose() {
  closing.value = true
  setTimeout(() => { open.value = false; closing.value = false }, 180)
}

function handleOpen() {
  syncToSelected()
  open.value = true
}

function onOutsideClick(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) handleClose()
}

function onKeydown(e) {
  if (!open.value) return
  if (e.key === 'Escape') { handleClose(); return }
  if (e.key === 'ArrowLeft') { e.preventDefault(); nav(-1) }
  if (e.key === 'ArrowRight') { e.preventDefault(); nav(1) }
}

onMounted(() => {
  document.addEventListener('mousedown', onOutsideClick)
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onOutsideClick)
  document.removeEventListener('keydown', onKeydown)
})

function nav(dir) {
  if (viewMode.value === 'days') {
    let m = viewMonth.value + dir
    if (m < 0) { viewMonth.value = 11; viewYear.value-- }
    else if (m > 11) { viewMonth.value = 0; viewYear.value++ }
    else viewMonth.value = m
  } else if (viewMode.value === 'months') {
    viewYear.value += dir
  } else {
    yearRange.value += dir * 12
  }
}

function emitDate(h, m) {
  const d = selectedDate.value || now
  const y = d.getFullYear(), mo = d.getMonth(), day = d.getDate()
  const nd = new Date(y, mo, day, h, m, 0)
  emit('update:modelValue', nd.toISOString())
}

function selectDay(d) {
  // Prevent future date selection
  if (d > now) return
  const df = fmt(d)
  // If selecting today, clamp time to now
  let h = selectedHour.value, m = selectedMin.value
  if (df === todayStr) {
    if (h > nowHour || (h === nowHour && m > nowMin)) {
      h = nowHour
      m = Math.floor(nowMin / 5) * 5
    }
  }
  const nd = new Date(d.getFullYear(), d.getMonth(), d.getDate(), h, m, 0)
  emit('update:modelValue', nd.toISOString())
  // 不关闭面板，方便继续调整时间；点击外部或按 Esc 关闭
}

function selectMonth(m) {
  // Prevent future month selection
  if (viewYear.value > now.getFullYear()) return
  if (viewYear.value === now.getFullYear() && m > now.getMonth()) return
  viewMonth.value = m; viewMode.value = 'days'
}

function selectYear(y) {
  if (y > now.getFullYear()) return
  viewYear.value = y; viewMode.value = 'months'
}

// Stepper for hours & minutes
const editHour = ref(false)
const editMin = ref(false)
const editHourVal = ref('')
const editMinVal = ref('')
const hourInputEl = ref(null)
const minInputEl = ref(null)

function stepHour(dir) {
  const df = selectedDate.value ? fmt(selectedDate.value) : ''
  let h = selectedHour.value + dir
  if (h < 0) h = 23
  if (h > 23) h = 0
  if (df === todayStr && h > nowHour) return
  emitDate(h, selectedMin.value)
}

function stepMin(dir) {
  const df = selectedDate.value ? fmt(selectedDate.value) : ''
  let m = selectedMin.value + dir * 5
  if (m < 0) m = 55
  if (m > 55) m = 0
  if (df === todayStr && selectedHour.value === nowHour && m > nowMin) return
  emitDate(selectedHour.value, m)
}

function startEditHour() {
  editHour.value = true
  editHourVal.value = String(selectedHour.value).padStart(2, '0')
  nextTick(() => { hourInputEl.value?.focus() })
}
function startEditMin() {
  editMin.value = true
  editMinVal.value = String(selectedMin.value).padStart(2, '0')
  nextTick(() => { minInputEl.value?.focus() })
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
  const df = selectedDate.value ? fmt(selectedDate.value) : ''
  if (df === todayStr && v > nowHour) v = nowHour
  emitDate(v, selectedMin.value)
}

function commitMin() {
  editMin.value = false
  let v = parseInt(editMinVal.value, 10)
  if (isNaN(v) || v < 0) v = 0
  if (v > 59) v = 59
  const df = selectedDate.value ? fmt(selectedDate.value) : ''
  if (df === todayStr && selectedHour.value === nowHour && v > nowMin) v = nowMin
  emitDate(selectedHour.value, v)
}

function onHourKey(e) {
  if (e.key === 'Enter') { commitHour() }
  if (e.key === 'Escape') { editHour.value = false }
}
function onMinKey(e) {
  if (e.key === 'Enter') { commitMin() }
  if (e.key === 'Escape') { editMin.value = false }
}

function selectNow() {
  emit('update:modelValue', new Date().toISOString())
  handleClose()
}

function selectClear() {
  emit('update:modelValue', '')
  handleClose()
}

// Max values for stepper (future-time guard)
const hourMax = computed(() => {
  const df = selectedDate.value ? fmt(selectedDate.value) : ''
  if (df === todayStr) return nowHour
  return 23
})

const minMax = computed(() => {
  const df = selectedDate.value ? fmt(selectedDate.value) : ''
  if (df === todayStr && selectedHour.value === nowHour) return nowMin
  return 59
})

// Calendar rendering
const dayCells = computed(() => {
  const firstDay = new Date(viewYear.value, viewMonth.value, 1).getDay()
  const daysInMonth = new Date(viewYear.value, viewMonth.value + 1, 0).getDate()
  const daysInPrev = new Date(viewYear.value, viewMonth.value, 0).getDate()
  const selStr = selectedDate.value ? fmt(selectedDate.value) : ''

  const cells = []
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({ day: daysInPrev - i, type: 'prev' })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(viewYear.value, viewMonth.value, d)
    const ds = fmt(date)
    const isFuture = date > now
    cells.push({
      day: d,
      type: 'current',
      isToday: ds === todayStr,
      isSel: ds === selStr,
      isFuture,
      date,
    })
  }
  const total = firstDay + daysInMonth
  const rem = total % 7 === 0 ? 0 : 7 - (total % 7)
  for (let d = 1; d <= rem; d++) {
    cells.push({ day: d, type: 'next' })
  }
  return cells
})

const monthCells = computed(() => {
  const cur = new Date()
  const curM = cur.getMonth(), curY = cur.getFullYear()
  const selD = selectedDate.value
  const selM = selD ? selD.getMonth() : -1, selY = selD ? selD.getFullYear() : -1
  return MONTHS.map((name, i) => ({
    name, idx: i,
    isCur: i === curM && viewYear.value === curY,
    isSel: i === selM && viewYear.value === selY,
    isFuture: viewYear.value > curY || (viewYear.value === curY && i > curM),
  }))
})

const yearCells = computed(() => {
  const curY = new Date().getFullYear()
  const selY = selectedDate.value ? selectedDate.value.getFullYear() : -1
  const cells = []
  for (let y = yearRange.value; y < yearRange.value + 12; y++) {
    cells.push({
      year: y,
      isCur: y === curY,
      isSel: y === selY,
      isFuture: y > curY,
    })
  }
  return cells
})

const headerLabel = computed(() => {
  if (viewMode.value === 'days') return `${viewYear.value}年 ${MONTHS[viewMonth.value]}`
  if (viewMode.value === 'months') return `${viewYear.value}年`
  return `${yearRange.value} - ${yearRange.value + 11}`
})

function onHeaderClick() {
  if (viewMode.value === 'days') viewMode.value = 'months'
  else if (viewMode.value === 'months') { viewMode.value = 'years'; yearRange.value = Math.floor(viewYear.value / 12) * 12 }
}

// Check if can navigate forward (future month/year guard)
const canNavForward = computed(() => {
  if (viewMode.value === 'days') {
    const nm = viewMonth.value + 1
    const ny = nm > 11 ? viewYear.value + 1 : viewYear.value
    const mi = nm > 11 ? 0 : nm
    return ny < now.getFullYear() || (ny === now.getFullYear() && mi <= now.getMonth())
  }
  if (viewMode.value === 'months') {
    return viewYear.value < now.getFullYear()
  }
  return yearRange.value + 12 <= now.getFullYear() + 12
})

const canNavBack = computed(() => {
  if (viewMode.value === 'years') return yearRange.value > 1900
  return viewYear.value > 1970
})
</script>

<template>
  <div ref="wrapperRef" class="dtp-wrapper">
    <div :class="['dtp-trigger', { open: open }]" @click="open ? handleClose() : handleOpen()">
      <span class="dtp-trigger-text">{{ displayText }}</span>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" :stroke="open ? ACCENT : '#94a3b8'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="dtp-icon">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    </div>
    <Transition name="dtp-drop">
      <div v-if="open" :class="['dtp-dropdown', { closing }]">
        <!-- Header -->
        <div class="dtp-header">
          <button class="dtp-nav-btn" :disabled="!canNavBack" @click="nav(-1)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 4 7 12 15 20" /></svg>
          </button>
          <div class="dtp-header-label" @click="onHeaderClick">{{ headerLabel }}</div>
          <button class="dtp-nav-btn" :disabled="!canNavForward" @click="nav(1)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 4 17 12 9 20" /></svg>
          </button>
        </div>

        <!-- Calendar body -->
        <div class="dtp-body">
          <!-- Day view -->
          <template v-if="viewMode === 'days'">
            <div class="dtp-weekdays">
              <div v-for="d in WEEKDAYS" :key="d" class="dtp-wd">{{ d }}</div>
            </div>
            <div class="dtp-days-grid">
              <div
                v-for="(c, i) in dayCells" :key="i"
                :class="[
                  'dtp-day',
                  { prev: c.type === 'prev', next: c.type === 'next', today: c.isToday, sel: c.isSel, future: c.isFuture }
                ]"
                @click="c.type === 'current' && !c.isFuture && selectDay(c.date)"
              >{{ c.day }}</div>
            </div>
          </template>

          <!-- Month view -->
          <div v-else-if="viewMode === 'months'" class="dtp-months-grid">
            <div
              v-for="c in monthCells" :key="c.idx"
              :class="['dtp-month', { cur: c.isCur, sel: c.isSel, future: c.isFuture }]"
              @click="!c.isFuture && selectMonth(c.idx)"
            >{{ c.name }}</div>
          </div>

          <!-- Year view -->
          <div v-else class="dtp-years-grid">
            <div
              v-for="c in yearCells" :key="c.year"
              :class="['dtp-year', { cur: c.isCur, sel: c.isSel, future: c.isFuture }]"
              @click="!c.isFuture && selectYear(c.year)"
            >{{ c.year }}</div>
          </div>
        </div>

        <!-- Time stepper -->
        <div class="dtp-time-sep"></div>
        <div class="dtp-time">
          <div class="dtp-time-label">时间</div>
          <div class="stepper-row">
            <!-- Hours -->
            <div class="stepper-col">
              <button class="stepper-btn" @click="stepHour(1)"
                :disabled="selectedHour >= hourMax">▲</button>
              <div class="stepper-val" @click="startEditHour" v-if="!editHour">
                {{ String(selectedHour).padStart(2,'0') }}
              </div>
              <input
                v-else
                ref="hourInputEl"
                class="stepper-input"
                :value="editHourVal"
                @input="onHourInput"
                @blur="commitHour"
                @keydown="onHourKey"
              />
              <button class="stepper-btn" @click="stepHour(-1)">▼</button>
            </div>
            <span class="stepper-colon">:</span>
            <!-- Minutes -->
            <div class="stepper-col">
              <button class="stepper-btn" @click="stepMin(1)"
                :disabled="selectedHour === hourMax && selectedMin >= minMax">▲</button>
              <div class="stepper-val" @click="startEditMin" v-if="!editMin">
                {{ String(selectedMin).padStart(2,'0') }}
              </div>
              <input
                v-else
                ref="minInputEl"
                class="stepper-input"
                :value="editMinVal"
                @input="onMinInput"
                @blur="commitMin"
                @keydown="onMinKey"
              />
              <button class="stepper-btn" @click="stepMin(-1)">▼</button>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="dtp-footer">
          <button class="dtp-btn dtp-btn-clear" @click="selectClear">清除</button>
          <button class="dtp-btn dtp-btn-now" @click="selectNow">此刻</button>
          <button class="dtp-btn dtp-btn-confirm" @click="handleClose">确定</button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dtp-wrapper { position: relative; width: 100%; }

.dtp-trigger {
  display: flex; align-items: center; justify-content: space-between;
  height: 38px; padding: 0 0.7rem;
  background: #f8fafc; border: 1.5px solid #e0e0e0;
  border-radius: 8px; cursor: pointer; font-size: 13px;
  color: #333;
  transition: border-color .15s, box-shadow .15s;
  user-select: none;
}
.dtp-trigger.open {
  border-color: #4f8ef7;
  box-shadow: 0 0 0 3px rgba(79,142,247,0.1);
}
.dtp-trigger-text {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: v-bind("selectedDate ? '#1e293b' : '#94a3b8'");
  font-weight: v-bind("selectedDate ? '500' : '400'");
}
.dtp-icon { flex-shrink: 0; margin-left: 6px; }

.dtp-dropdown {
  position: absolute; top: calc(100% + 8px); left: 50%; transform: translateX(-50%);
  background: #fff; border: 1px solid #e8e8e8; border-radius: 14px;
  padding: 16px 18px 12px; width: 340px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.1), 0 2px 8px rgba(0,0,0,0.06);
  z-index: 2000;
}

.dtp-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
}
.dtp-nav-btn {
  width: 32px; height: 32px; border: none; background: transparent;
  border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: #94a3b8; transition: background .15s, color .15s;
}
.dtp-nav-btn:hover:not(:disabled) { background: #f5f6f8; color: #555; }
.dtp-nav-btn:disabled { opacity: 0.3; cursor: default; }
.dtp-header-label {
  font-size: 14px; font-weight: 600; color: #1e293b; cursor: pointer;
  padding: 4px 10px; border-radius: 8px; transition: background .12s;
}
.dtp-header-label:hover { background: #f5f6f8; }

.dtp-body { min-height: 240px; }

.dtp-weekdays {
  display: grid; grid-template-columns: repeat(7, 1fr); text-align: center;
  margin-bottom: 4px;
}
.dtp-wd { font-size: 11px; font-weight: 600; color: #94a3b8; padding-bottom: 4px; }

.dtp-days-grid {
  display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px;
}
.dtp-day {
  aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  font-size: 13px; border-radius: 8px; cursor: pointer; position: relative;
  transition: background .12s; color: #1e293b;
}
.dtp-day:hover { background: #f0f3f8; }
.dtp-day.prev, .dtp-day.next { color: #cbd5e1; pointer-events: none; }
.dtp-day.future { color: #d0d5dd; pointer-events: none; }
.dtp-day.today { color: #4f8ef7; font-weight: 600; }
.dtp-day.sel { background: #4f8ef7; color: #fff; font-weight: 600; box-shadow: 0 3px 10px rgba(79,142,247,0.25); }
.dtp-day.sel:hover { background: #3b7de6; }
.dtp-day.today:not(.sel)::after {
  content: ''; position: absolute; bottom: 3px; width: 4px; height: 4px;
  border-radius: 50%; background: #4f8ef7; opacity: 0.6;
}

.dtp-months-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
  padding: 4px 0;
}
.dtp-month {
  padding: 12px 4px; display: flex; align-items: center; justify-content: center;
  font-size: 13px; border-radius: 10px; cursor: pointer;
  border: 1.5px solid transparent; transition: all .12s;
  color: #1e293b;
}
.dtp-month:hover { background: #f0f3f8; }
.dtp-month.cur { background: #eff3ff; color: #4f8ef7; font-weight: 500; border-color: #eff3ff; }
.dtp-month.sel { background: #4f8ef7; color: #fff; font-weight: 600; border-color: #4f8ef7; box-shadow: 0 3px 10px rgba(79,142,247,0.25); }
.dtp-month.future { color: #d0d5dd; pointer-events: none; }

.dtp-years-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
  padding: 4px 0; max-height: 200px; overflow-y: auto;
}
.dtp-year {
  padding: 10px 4px; display: flex; align-items: center; justify-content: center;
  font-size: 13px; border-radius: 10px; cursor: pointer;
  border: 1.5px solid transparent; transition: all .12s;
  color: #1e293b;
}
.dtp-year:hover { background: #f0f3f8; }
.dtp-year.cur { background: #eff3ff; color: #4f8ef7; font-weight: 500; border-color: #eff3ff; }
.dtp-year.sel { background: #4f8ef7; color: #fff; font-weight: 600; border-color: #4f8ef7; box-shadow: 0 3px 10px rgba(79,142,247,0.25); }
.dtp-year.future { color: #d0d5dd; pointer-events: none; }

.dtp-time-sep { height: 1px; background: #f0f0f0; margin: 10px 0; }

.dtp-time { padding: 4px 0; }
.dtp-time-label { font-size: 11px; font-weight: 600; color: #94a3b8; margin-bottom: 10px; text-align: center; }

.stepper-row {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  font-variant-numeric: tabular-nums;
}
.stepper-colon {
  font-size: 22px; font-weight: 600; color: #bbb; padding-bottom: 6px;
}
.stepper-col {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.stepper-btn {
  width: 56px; height: 28px; border: 1px solid #e8e8e8; background: #fafbfc;
  border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: #888; transition: all .12s; user-select: none;
  line-height: 1; padding: 0;
}
.stepper-btn:hover:not(:disabled) { background: #eff3ff; border-color: #4f8ef7; color: #4f8ef7; }
.stepper-btn:disabled { opacity: .3; cursor: default; }

.stepper-val {
  width: 56px; height: 46px; display: flex; align-items: center; justify-content: center;
  font-size: 26px; font-weight: 700; color: #1e293b; letter-spacing: -1px;
  background: #f8fafc; border: 1.5px solid transparent; border-radius: 8px;
  cursor: pointer; transition: all .12s; user-select: none;
}
.stepper-val:hover { border-color: #4f8ef7; background: #fff; }

.stepper-input {
  width: 56px; height: 46px; text-align: center;
  font-size: 26px; font-weight: 700; color: #1e293b; letter-spacing: -1px;
  background: #fff; border: 1.5px solid #4f8ef7; border-radius: 8px;
  outline: none; font-family: inherit; font-variant-numeric: tabular-nums;
  box-shadow: 0 0 0 3px rgba(79,142,247,0.12);
}
.stepper-input:focus { border-color: #4f8ef7; }

.dtp-footer { display: flex; gap: 8px; margin-top: 12px; }
.dtp-btn {
  flex: 1; padding: 8px 0; font-size: 13px; font-weight: 600;
  border-radius: 8px; cursor: pointer; border: none; transition: all .12s;
}
.dtp-btn-now { background: #eff3ff; color: #4f8ef7; }
.dtp-btn-now:hover { background: #dce6fd; }
.dtp-btn-clear { background: transparent; border: 1px solid #e0e0e0; color: #888; }
.dtp-btn-clear:hover { background: #f5f6f8; }
.dtp-btn-confirm { background: #4f8ef7; color: #fff; }
.dtp-btn-confirm:hover { background: #3b7de6; }

.dtp-drop-enter-active { animation: dtp-in .18s ease; }
.dtp-drop-leave-active { animation: dtp-out .18s ease; }
@keyframes dtp-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-4px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
@keyframes dtp-out {
  from { opacity: 1; transform: translateX(-50%) translateY(0); }
  to { opacity: 0; transform: translateX(-50%) translateY(-4px); }
}
</style>
