<script setup>
import { computed } from 'vue'

const props = defineProps({ snapshot: Object })

const fmt = n => n != null ? Number(n).toLocaleString() : '-'

const cards = computed(() => {
  const d = props.snapshot || {}
  return [
    { label: '播放', value: fmt(d.view_count), score: d.score_play != null ? `得点 ${fmt(d.score_play)}` : '' },
    { label: '弹幕', value: fmt(d.danmaku), score: '' },
    { label: '评论', value: fmt(d.reply), score: '' },
    { label: '收藏', value: fmt(d.favorite), score: d.score_fav != null ? `得点 ${fmt(d.score_fav)}` : '' },
    { label: '硬币', value: fmt(d.coin), score: d.score_coin != null ? `得点 ${fmt(d.score_coin)}` : '' },
    { label: '点赞', value: fmt(d.like_count), score: d.score_like != null ? `得点 ${fmt(d.score_like)}` : '' },
    { label: '分享', value: fmt(d.share), score: '' },
    { label: '正在观看', value: d.online_total ?? '-', score: '' },
    { label: '最终得点', value: d.score_total != null ? fmt(d.score_total) : '-', score: '', total: true },
  ]
})
</script>

<template>
  <div class="cards">
    <div v-for="c in cards" :key="c.label" :class="['card', { total: c.total }]">
      <div class="label">{{ c.label }}</div>
      <div class="value">{{ c.value }}</div>
      <div v-if="c.score" class="score">{{ c.score }}</div>
    </div>
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
@media (max-width: 640px) {
  .cards { grid-template-columns: repeat(3, 1fr); }
}
</style>
