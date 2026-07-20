/**
 * 纯前端搜索：在 uploaders 分组数据中搜索 UP主名 / 视频标题 / BV号 / 发布者名
 * 返回混合结果列表：UP主在前，视频在后，视频自动去重
 */
export function searchUploaders(uploaders, query) {
  if (!query || !query.trim()) return []

  const q = query.trim().toLowerCase()
  const seenVideoIds = new Set()

  // 建立 video_id → owner_mid 映射（分组数据中 v.role === 'owner' 时，当前 u.mid 即 owner）
  // 同时建立 video_id → uploaders 列表映射（用于显示发布者）
  const videoOwnerMap = new Map()
  const videoUploadersMap = new Map()
  for (const u of uploaders) {
    for (const v of u.videos) {
      if (!videoUploadersMap.has(v.id)) {
        videoUploadersMap.set(v.id, [])
      }
      videoUploadersMap.get(v.id).push({ mid: u.mid, name: u.name, face: u.face, role: v.role || 'staff' })
      if (v.role === 'owner') {
        videoOwnerMap.set(v.id, u.mid)
      }
    }
  }

  /** @type {Array<{type:'uploader'|'video'}>} */
  const uploaderResults = []
  const videoResults = []

  for (const u of uploaders) {
    const nameMatch = u.name.toLowerCase().includes(q)

    // UP主名匹配 → 添加上传者条目
    if (nameMatch) {
      uploaderResults.push({
        type: 'uploader',
        mid: u.mid,
        name: u.name,
        face: u.face,
        videoCount: u.videos.length,
        videos: u.videos,
      })
    }

    // 遍历该UP主的所有视频
    for (const v of u.videos) {
      if (seenVideoIds.has(v.id)) continue

      const titleMatch = (v.title || '').toLowerCase().includes(q)
      const bvidMatch = v.bvid.toLowerCase().includes(q)
      // 如果UP主名匹配了，该UP主的所有视频都加入视频结果
      const publisherMatch = nameMatch

      if (titleMatch || bvidMatch || publisherMatch) {
        seenVideoIds.add(v.id)
        videoResults.push({
          type: 'video',
          id: v.id,
          bvid: v.bvid,
          title: v.title || v.bvid,
          pic: v.pic,
          uploaders: videoUploadersMap.get(v.id) || [],
          paused: v.paused,
          score_enabled: v.score_enabled,
          rule_group_id: v.rule_group_id,
          snapshot_count: v.snapshot_count,
          last_snapshot_at: v.last_snapshot_at,
          // 导航到 owner 的 mid
          _searchUploaderMid: videoOwnerMap.get(v.id) || u.mid,
        })
      }
    }
  }

  // UP主按名称排序
  uploaderResults.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  // 视频按标题排序
  videoResults.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'))

  return [...uploaderResults, ...videoResults]
}
