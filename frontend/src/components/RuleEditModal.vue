<script setup>
import { ref, watch } from 'vue'
import Dropdown from './Dropdown.vue'
import TimePicker from './TimePicker.vue'

const props = defineProps({
  show: Boolean,
  rule: Object,           // null = add mode; {rule_type, value_json} = edit mode
  ruleTypeOptions: Array,  // [{value, label}]
  metricOptions: Array,    // [{value, label}]
  dowOptions: Array,       // [{value, label}]
})

const emit = defineEmits(['close', 'save'])

// Form state
const ruleType = ref(1)
const ruleInterval = ref(60)
const ruleCondMetric = ref('view_count')
const ruleCondMin = ref(null)
const ruleCondMax = ref(null)
const ruleCondInterval = ref(30)
const ruleTime = ref('03:00')
const ruleDow = ref(5)
const formError = ref('')

function resetForm() {
  ruleType.value = 1; ruleInterval.value = 60
  ruleCondMetric.value = 'view_count'
  ruleCondMin.value = null; ruleCondMax.value = null
  ruleCondInterval.value = 30
  ruleTime.value = '03:00'; ruleDow.value = 5
  formError.value = ''
}

function loadRule(r) {
  if (!r) { resetForm(); return }
  ruleType.value = r.rule_type
  if (r.rule_type === 1) {
    ruleInterval.value = r.interval || 60
  } else if (r.rule_type === 2) {
    ruleCondMetric.value = r.metric || 'view_count'
    ruleCondMin.value = r.min_value ?? null
    ruleCondMax.value = r.max_value ?? null
    ruleCondInterval.value = r.target_interval || 30
  } else if (r.rule_type === 3) {
    ruleTime.value = r.time || '00:00'
  } else if (r.rule_type === 4) {
    ruleDow.value = r.day_of_week ?? 5
    ruleTime.value = r.time || '03:00'
  }
}

watch(() => props.show, (v) => {
  if (v) {
    loadRule(props.rule)
  }
})

function doSave() {
  formError.value = ''
  let value = {}
  if (ruleType.value === 1) {
    value = { interval: Math.max(30, ruleInterval.value) }
  } else if (ruleType.value === 2) {
    const minRaw = ruleCondMin.value !== null && ruleCondMin.value !== '' ? Number(ruleCondMin.value) : null
    const maxRaw = ruleCondMax.value !== null && ruleCondMax.value !== '' ? Number(ruleCondMax.value) : null
    if (minRaw == null && maxRaw == null) {
      formError.value = '请至少填写区间的一端'
      return
    }
    if (minRaw != null && (isNaN(minRaw) || minRaw < 0)) {
      formError.value = '区间左端点不能为负数'
      return
    }
    if (maxRaw != null && (isNaN(maxRaw) || maxRaw <= 0)) {
      formError.value = '区间右端点必须大于 0'
      return
    }
    if (minRaw != null && maxRaw != null && minRaw >= maxRaw) {
      formError.value = '区间左端点必须小于右端点'
      return
    }
    const minVal = minRaw
    const maxVal = maxRaw
    value = {
      metric: ruleCondMetric.value,
      min_value: minVal,
      max_value: maxVal,
      target_interval: Math.max(30, ruleCondInterval.value),
    }
  } else if (ruleType.value === 3) {
    value = { time: ruleTime.value }
  } else if (ruleType.value === 4) {
    value = { day_of_week: ruleDow.value, time: ruleTime.value }
  }
  emit('save', { type: ruleType.value, value })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay" @click.self="emit('close')">
        <div class="modal-box">
          <h2>{{ rule ? '编辑规则' : '添加规则' }}</h2>

          <div class="form-row">
            <label>类型</label>
            <Dropdown :options="ruleTypeOptions" v-model="ruleType" />
          </div>

          <!-- Type 1: 定长 -->
          <div v-if="ruleType === 1" class="form-row">
            <label>间隔</label>
            <input type="number" v-model.number="ruleInterval" min="30" />
            <span class="unit">秒</span>
          </div>

          <!-- Type 2: 条件精确 -->
          <template v-if="ruleType === 2">
            <div class="form-row">
              <label>指标</label>
              <Dropdown :options="metricOptions" v-model="ruleCondMetric" />
            </div>
            <div class="form-row">
              <label>区间</label>
              <span class="bracket">[</span>
              <input type="number" v-model.number="ruleCondMin" placeholder="不限" class="range-input" min="0" />
              <span class="range-sep">,</span>
              <input type="number" v-model.number="ruleCondMax" placeholder="不限" class="range-input" min="0" />
              <span class="bracket">]</span>
            </div>
            <p v-if="formError" class="form-error">{{ formError }}</p>
            <div class="form-row">
              <label>步长</label>
              <input type="number" v-model.number="ruleCondInterval" min="30" />
              <span class="unit">秒（条件成立时）</span>
            </div>
          </template>

          <!-- Type 3: 每天某点 -->
          <div v-if="ruleType === 3" class="form-row">
            <label>时间</label>
            <TimePicker v-model="ruleTime" />
          </div>

          <!-- Type 4: 每周定点 -->
          <div v-if="ruleType === 4" class="form-row">
            <label>时间</label>
            <Dropdown :options="dowOptions" v-model="ruleDow" style="min-width:70px" />
            <TimePicker v-model="ruleTime" />
          </div>

          <div class="actions">
            <button class="btn-cancel" @click="emit('close')">取消</button>
            <button class="btn-save" @click="doSave">{{ rule ? '更新' : '添加' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 220;
  display: flex; align-items: center; justify-content: center;
  background: var(--overlay); backdrop-filter: blur(3px);
}
.modal-box {
  background: var(--surface); border-radius: 14px; padding: 28px 32px;
  width: 420px; max-width: 94vw;
  box-shadow: var(--shadow-lg);
}
h2 { font-size: 17px; font-weight: 700; margin: 0 0 20px; }

.form-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
}
.form-row label {
  font-size: 13px; font-weight: 500; color: var(--text-muted);
  min-width: 48px; flex-shrink: 0;
}
.form-row input[type="number"] {
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px;
  font-size: 13px; outline: none; background: var(--surface);
  color: var(--text); width: 90px;
}
.form-row input:focus { border-color: var(--accent); }
.unit { font-size: 12px; color: var(--text-muted); }
.range-input { width: 100px !important; }
.bracket { font-size: 14px; font-weight: 600; color: var(--text-placeholder); }
.range-sep { font-size: 12px; color: var(--text-placeholder); margin: 0 2px; }
.form-error { font-size: 12px; color: var(--red); margin: 0 0 4px 56px; }

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }

.btn-save {
  border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px;
  cursor: pointer; font-weight: 500; background: var(--accent); color: #fff;
  transition: all .15s;
}
.btn-save:hover { background: var(--accent-hover); }

.btn-cancel {
  border: 1px solid var(--border); border-radius: 7px; padding: 8px 24px;
  font-size: 13px; cursor: pointer; font-weight: 500;
  background: var(--surface); color: var(--text-muted); transition: all .12s;
}
.btn-cancel:hover { background: var(--surface-hover); }

/* Transition */
.modal-enter-active { transition: opacity .2s; }
.modal-leave-active { transition: opacity .15s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .2s, transform .25s cubic-bezier(.34,1.56,.64,1); }
.modal-leave-active .modal-box { transition: opacity .15s, transform .15s ease; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.88) translateY(-8px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.95); }
</style>
