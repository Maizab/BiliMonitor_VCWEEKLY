<script setup>
import { ref, watch } from 'vue'
import { loadFormatMode, saveFormatMode } from '../composables/useNumberFormat.js'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['close'])

const THEME_KEY = 'app-theme'
const themes = [
  { value: 'auto', label: '跟随系统' },
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
]
const numFormats = [
  { value: 'cn', label: '中文计数（万/亿）' },
  { value: 'en', label: '英文计数（K/M/B）' },
  { value: 'full', label: '完整数字' },
]

const current = ref('auto')
const numFmt = ref('full')

function loadTheme() {
  try {
    const v = localStorage.getItem(THEME_KEY)
    if (v && themes.some(t => t.value === v)) return v
  } catch (e) { /* ignore */ }
  return 'auto'
}

function applyTheme(v) {
  if (v === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else if (v === 'light') {
    document.documentElement.setAttribute('data-theme', 'light')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

function setTheme(v) {
  current.value = v
  try { localStorage.setItem(THEME_KEY, v) } catch (e) { /* ignore */ }
  applyTheme(v)
}

function setNumFmt(v) {
  numFmt.value = v
  saveFormatMode(v)
}

watch(() => props.show, (v) => {
  if (v) {
    current.value = loadTheme()
    numFmt.value = loadFormatMode()
  }
})

// 初始化
applyTheme(loadTheme())
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay">
        <div class="modal-box">
          <h2>设置</h2>

          <section class="section">
            <h3>主题</h3>
            <div class="theme-options">
              <label v-for="t in themes" :key="t.value" class="theme-option">
                <input type="radio" :value="t.value" v-model="current" @change="setTheme(t.value)" />
                <span class="radio-mark"></span>
                {{ t.label }}
              </label>
            </div>
          </section>

          <section class="section">
            <h3>数字格式</h3>
            <div class="theme-options">
              <label v-for="f in numFormats" :key="f.value" class="theme-option">
                <input type="radio" :value="f.value" v-model="numFmt" @change="setNumFmt(f.value)" />
                <span class="radio-mark"></span>
                {{ f.label }}
              </label>
            </div>
          </section>

          <div class="actions">
            <button class="btn-primary" @click="emit('close')">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 200;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 10vh;
  background: var(--overlay); backdrop-filter: blur(3px);
  overflow-y: auto;
}
.modal-box {
  background: var(--surface); border-radius: 14px; padding: 28px 32px;
  width: 440px; max-width: 94vw;
  box-shadow: var(--shadow-lg); position: relative;
}
h2 { font-size: 17px; font-weight: 700; margin-bottom: 20px; }

.section { margin-bottom: 18px; }
.section h3 { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 10px; }

.theme-options { display: flex; flex-direction: column; gap: 4px; }
.theme-option {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text);
  transition: background .12s; user-select: none;
}
.theme-option:hover { background: var(--surface-hover); }
.theme-option input { position: absolute; opacity: 0; width: 0; height: 0; }
.radio-mark {
  width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--border);
  flex-shrink: 0; transition: all .15s; position: relative;
}
.theme-option input:checked + .radio-mark {
  border-color: var(--accent); border-width: 5px;
}

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 4px; }
.btn-primary { border: none; border-radius: 7px; padding: 8px 24px; font-size: 13px; cursor: pointer; font-weight: 500; background: var(--accent); color: #fff; transition: all .15s; }
.btn-primary:hover { background: var(--accent-hover); }

/* Transition */
.modal-enter-active { transition: opacity .25s; }
.modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { transition: opacity .25s, transform .25s; }
.modal-leave-active .modal-box { transition: opacity .2s, transform .2s; }
.modal-enter-from .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
.modal-leave-to .modal-box { opacity: 0; transform: scale(.92) translateY(-12px); }
</style>
