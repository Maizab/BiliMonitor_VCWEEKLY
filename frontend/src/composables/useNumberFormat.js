import { ref } from 'vue'

const KEY = 'number-format'

function loadMode() {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'en' || v === 'cn' || v === 'full') return v
    // 兼容旧值 'si'
    if (v === 'si') return 'en'
  } catch (e) { /* ignore */ }
  return 'cn'
}

// 全局响应式状态，更改时所有组件自动更新
const mode = ref(loadMode())

export function loadFormatMode() { return mode.value }
export function saveFormatMode(v) {
  mode.value = v
  try { localStorage.setItem(KEY, v) } catch (e) { /* ignore */ }
}

function fmtFull(n) {
  if (n == null) return '-'
  return Number(n).toLocaleString()
}

const EN_SYMBOLS = ['', 'K', 'M', 'B']

function fmtEN(n) {
  if (n == null) return '-'
  if (n === 0) return '0'
  const sign = n < 0 ? '-' : ''
  n = Math.abs(n)
  if (n < 1000) return sign + String(n)
  const exp = Math.floor(Math.log10(n))
  const enIdx = Math.min(Math.floor(exp / 3), EN_SYMBOLS.length - 1)
  const divisor = Math.pow(10, enIdx * 3)
  return sign + (n / divisor).toPrecision(4) + EN_SYMBOLS[enIdx]
}

function fmtCN(n) {
  if (n == null) return '-'
  if (n === 0) return '0'
  const sign = n < 0 ? '-' : ''
  n = Math.abs(n)
  if (n < 10000) return sign + String(n)
  const WW = 10000, YY = 100000000
  if (n >= YY) return sign + (n / YY).toPrecision(4) + '亿'
  return sign + (n / WW).toPrecision(4) + '万'
}

function formatNum(n, m) {
  if (m === 'en') return fmtEN(n)
  if (m === 'cn') return fmtCN(n)
  return fmtFull(n)
}

export function useNumberFormat() {
  const fmt = (n) => formatNum(n, mode.value)
  return { fmt, mode }
}

