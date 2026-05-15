<script setup>
import { computed } from 'vue'

const props = defineProps({
  snapshot: Object,
  loading: { type: Boolean, default: false },
  scoreEnabled: { type: Boolean, default: true },
})

const fmt = n => n != null ? Number(n).toLocaleString() : '-'

const cards = computed(() => {
  const d = props.snapshot || {}
  const se = props.scoreEnabled
  const items = [
    { label: '播放', value: fmt(d.view_count), score: se && d.score_play != null ? `得点 ${fmt(d.score_play)}` : '' },
    { label: '弹幕', value: fmt(d.danmaku), score: '' },
    { label: '评论', value: fmt(d.reply), score: '' },
    { label: '收藏', value: fmt(d.favorite), score: se && d.score_fav != null ? `得点 ${fmt(d.score_fav)}` : '' },
    { label: '硬币', value: fmt(d.coin), score: se && d.score_coin != null ? `得点 ${fmt(d.score_coin)}` : '' },
    { label: '点赞', value: fmt(d.like_count), score: se && d.score_like != null ? `得点 ${fmt(d.score_like)}` : '' },
    { label: '分享', value: fmt(d.share), score: '' },
    { label: '正在观看', value: d.online_total ?? '-', score: '' },
  ]
  if (se) {
    items.push({ label: '最终得点', value: d.score_total != null ? fmt(d.score_total) : '-', score: '', total: true })
  }
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
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(125px, 1fr)); gap: 8px; }
.card { background: #fff; border-radius: 10px; padding: 12px 14px; box-shadow: 0 1px 4px rgba(0,0,0,.04); transition: box-shadow .2s, transform .15s; }
.card:hover { box-shadow: 0 2px 10px rgba(0,0,0,.08); transform: translateY(-1px); }
.card .label { font-size: 11px; color: #aaa; margin-bottom: 4px; font-weight: 500; }
.card .value { font-size: 20px; font-weight: 700; letter-spacing: -.3px; }
.card .score { font-size: 11px; color: #999; margin-top: 2px; }
.card.total { background: linear-gradient(135deg, #4f8ef7, #6c5ce7); border: none; }
.card.total .label { color: #ffffffaa; }
.card.total .value { color: #fff; font-size: 22px; }
.card.skeleton { min-height: 72px; display: flex; flex-direction: column; gap: 6px; }
.sk-line { height: 12px; border-radius: 4px; background: #e8e8e8; animation: sk-pulse 1.5s ease-in-out infinite; }
.sk-line.w30 { width: 30%; }
.sk-line.w40 { width: 40%; }
.sk-line.w80 { width: 80%; }
@keyframes sk-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

@media (max-width: 640px) {
  .cards { grid-template-columns: repeat(3, 1fr); }
}
</style>
