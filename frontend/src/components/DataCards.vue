<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
  snapshot: Object,
  reference: Object,
  loading: { type: Boolean, default: false },
  scoreEnabled: { type: Boolean, default: true },
})

const fmtNum = inject('fmtNum', n => n != null ? Number(n).toLocaleString() : '-')
const fmt = n => n != null ? fmtNum(n) : '-'

const incrFmt = (key) => {
  if (!props.reference) return '—'
  const v = props.snapshot?.[key]
  if (v == null) return '—'
  return fmt(v)
}

const incrScoreFmt = (key) => {
  if (!props.reference) return '—'
  const v = props.snapshot?.[key]
  if (v == null) return '—'
  return fmtNum(v)
}

const hasRef = computed(() => !!props.reference)

const cards = computed(() => {
  const d = props.snapshot || {}
  const se = props.scoreEnabled
  const items = [
    { label: '播放', value: fmt(d.view_count), score: se && d.score_play != null ? `积累得点 ${fmt(d.score_play)}` : '' },
    { label: '弹幕', value: fmt(d.danmaku), score: '' },
    { label: '评论', value: fmt(d.reply), score: '' },
    { label: '收藏', value: fmt(d.favorite), score: se && d.score_fav != null ? `积累得点 ${fmt(d.score_fav)}` : '' },
    { label: '硬币', value: fmt(d.coin), score: se && d.score_coin != null ? `积累得点 ${fmt(d.score_coin)}` : '' },
    { label: '点赞', value: fmt(d.like_count), score: se && d.score_like != null ? `积累得点 ${fmt(d.score_like)}` : '' },
    { label: '分享', value: fmt(d.share), score: '' },
    { label: '正在观看人数', value: fmt(d.online_total), score: '' },
  ]
  if (se) {
    items.push({ label: '最终积累得点', value: d.score_total != null ? fmt(d.score_total) : '-', score: '', total: true })
  }
  return items
})

const incrCards = computed(() => {
  if (!props.scoreEnabled) return []
  const d = props.snapshot || {}
  const ref = props.reference
  const items = [
    { label: '播放增量', value: incrFmt('incr_view_count'), score: ref ? `增量得点 ${incrScoreFmt('incr_score_play')}` : '' },
    { label: '弹幕增量', value: incrFmt('incr_danmaku'), score: '' },
    { label: '评论增量', value: incrFmt('incr_reply'), score: '' },
    { label: '收藏增量', value: incrFmt('incr_favorite'), score: ref ? `增量得点 ${incrScoreFmt('incr_score_fav')}` : '' },
    { label: '硬币增量', value: incrFmt('incr_coin'), score: ref ? `增量得点 ${incrScoreFmt('incr_score_coin')}` : '' },
    { label: '点赞增量', value: incrFmt('incr_like_count'), score: ref ? `增量得点 ${incrScoreFmt('incr_score_like')}` : '' },
    { label: '分享增量', value: incrFmt('incr_share'), score: '' },
  ]
  items.push({ label: '最终增量得点', value: ref && d.incr_score_total != null ? incrScoreFmt('incr_score_total') : '—', score: '', total: true })
  return items
})
</script>

<template>
  <div class="cards">
    <template v-if="loading">
      <div v-for="i in 9" :key="'sk'+i" class="card skeleton">
        <div class="sk-line w30"></div>
        <div class="sk-line w80"></div>
        <div class="sk-line w40"></div>
      </div>
    </template>
    <template v-else>
      <div v-for="c in cards" :key="c.label" :class="['card', { total: c.total }]">
        <div class="label">{{ c.label }}</div>
        <div class="value">{{ c.value }}</div>
        <div v-if="c.score" class="score">{{ c.score }}</div>
      </div>
    </template>
  </div>

  <div v-if="scoreEnabled && !loading" class="incr-section">
    <div class="incr-header">
      <span class="incr-title">本期增量得点</span>
      <span v-if="!hasRef" class="incr-hint">（未记录到上周六 03:00 附近的数据，无法计算增量）</span>
    </div>
    <div class="cards incr-cards">
      <div v-for="c in incrCards" :key="c.label" :class="['card', 'incr-card', { total: c.total }]">
        <div class="label">{{ c.label }}</div>
        <div class="value incr-value">{{ c.value }}</div>
        <div v-if="c.score" class="score">{{ c.score }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(125px, 1fr)); gap: 8px; }
.card { background: var(--surface); border-radius: 10px; padding: 12px 14px; box-shadow: var(--shadow); transition: box-shadow .2s, transform .15s; }
.card:hover { box-shadow: 0 2px 10px rgba(0,0,0,.08); transform: translateY(-1px); }
.card .label { font-size: 11px; color: var(--text-placeholder); margin-bottom: 4px; font-weight: 500; }
.card .value { font-size: 20px; font-weight: 700; letter-spacing: -.3px; overflow-x: auto; white-space: nowrap; }
.card .score { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.card.total { background: linear-gradient(135deg, #4f8ef7, #6c5ce7); border: none; }
.card.total .label { color: #ffffffaa; }
.card.total .value { color: #fff; font-size: 22px; }
.card.skeleton { min-height: 72px; display: flex; flex-direction: column; gap: 6px; }
.sk-line { height: 12px; border-radius: 4px; background: var(--border); animation: sk-pulse 1.5s ease-in-out infinite; }
.sk-line.w30 { width: 30%; }
.sk-line.w40 { width: 40%; }
.sk-line.w80 { width: 80%; }
@keyframes sk-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.incr-section { margin-top: 6px; }
.incr-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.incr-title { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.incr-hint { font-size: 10px; color: var(--text-placeholder); }
.incr-cards { margin-top: 0; }
.incr-card .value { font-size: 18px; }
.incr-value { color: v-bind("hasRef ? 'inherit' : 'var(--text-placeholder)'"); }

@media (max-width: 640px) {
  .cards { grid-template-columns: repeat(3, 1fr); }
}
</style>
