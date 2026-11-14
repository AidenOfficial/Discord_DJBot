// Activity 模式下图片的 blob 缓存(AuthImg 用):同一地址只取一次,最多留 MAX 张,淘汰时释放 blob URL。
import { apiFetch } from './api'

const MAX = 300
const cache = new Map<string, Promise<string | null>>()

// priority:跟着 <img fetchpriority> 走(主封面 high),浏览器不支持就忽略。只影响第一次取。
export function authedImage(url: string, priority?: RequestPriority): Promise<string | null> {
  const hit = cache.get(url)
  if (hit) {
    cache.delete(url) // 挪到最后:最近用过
    cache.set(url, hit)
    return hit
  }
  const p = apiFetch(url, priority ? { priority } : {})
    .then(async (rv) => (rv.ok ? URL.createObjectURL(await rv.blob()) : null))
    .catch(() => null)
  cache.set(url, p)
  // 取失败的不缓存,下次再试
  p.then((v) => { if (v === null && cache.get(url) === p) cache.delete(url) })
  while (cache.size > MAX) {
    const [oldest, old] = cache.entries().next().value as [string, Promise<string | null>]
    cache.delete(oldest)
    old.then((v) => { if (v) URL.revokeObjectURL(v) })
  }
  return p
}
