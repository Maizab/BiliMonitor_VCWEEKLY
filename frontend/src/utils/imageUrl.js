/**
 * Bilibili CDN 图片 URL 构建工具
 *
 * B站 CDN 支持通过 URL 后缀指定图片尺寸和格式：
 * - 头像: @128w_128h_1c_1s.webp (1c=居中裁剪, 1s=锐化)
 * - 封面: @672w_378h_1c.avif / @672w_378h_1c.webp
 *
 * 所有 <img> 标签需设置 referrerpolicy="no-referrer" 以隐藏来源域名。
 */

/**
 * 将上传者头像 URL 转为指定尺寸的 webp URL
 * @param {string} face - 头像原始路径（如 "//i1.hdslb.com/bfs/face/xxx.jpg"）
 * @returns {string} 转换后的 CDN URL
 */
export function avatarUrl(face) {
  if (!face) return ''
  let path = face
  // 补齐 https 协议
  if (path.startsWith('//')) path = 'https:' + path
  if (path.startsWith('http://')) path = path.replace('http://', 'https://')
  // 去掉已有的 @ 后缀
  path = path.replace(/@.*$/, '')
  return path + '@96w_96h_1c_1s.webp'
}

/**
 * 将视频封面 URL 转为指定尺寸的 avif/webp URL
 * @param {string} pic - 封面原始路径（如 "//i0.hdslb.com/bfs/archive/xxx.jpg"）
 * @param {string} size - 目标尺寸，默认 "672w_378h"
 * @returns {{ avif: string, webp: string }}
 */
export function coverUrls(pic, size = '672w_378h') {
  if (!pic) return { avif: '', webp: '' }
  let path = pic
  if (path.startsWith('//')) path = 'https:' + path
  if (path.startsWith('http://')) path = path.replace('http://', 'https://')
  path = path.replace(/@.*$/, '')
  return {
    avif: path + `@${size}_1c.avif`,
    webp: path + `@${size}_1c.webp`,
  }
}

/**
 * 判断视频是否为合作视频（有多个参与者）
 * @param {object} video - 包含 uploaders 数组的视频对象
 * @returns {boolean}
 */
export function isCollaboration(video) {
  return video.uploaders && video.uploaders.length > 1
}
