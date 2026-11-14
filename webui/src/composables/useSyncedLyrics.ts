// 带时间轴的歌词,和播放进度对上的那一行(画中画小窗用)。
// 和 LyricsPanel 同样的取法:状态轮询里 current.lyrics 变成 found / instrumental 才去取。
// 只返回能跟着播放走的歌词;只有纯文本、时间轴对不上的,当成没有。
import { computed, ref, watch, type Ref } from 'vue'
import { fetchLyrics, type CurrentItem, type Lyrics } from '../api'
import { useStatus } from './useStatus'

let last: { id: string; data: Lyrics } | null = null

export function useSyncedLyrics(current: Ref<CurrentItem | null>) {
  const { clock } = useStatus()
  const lyrics = ref<Lyrics | null>(null)
  const loadedFor = ref('')

  watch(
    () => [current.value?.id ?? '', current.value?.lyrics] as const,
    async ([id, state]) => {
      if (loadedFor.value !== id) {
        lyrics.value = null
        loadedFor.value = ''
      }
      if (!id || state !== 'found' || loadedFor.value === id) return
      if (last?.id === id) {
        lyrics.value = last.data
        loadedFor.value = id
      }
      try {
        const data = await fetchLyrics(id)
        if (current.value?.id !== id) return
        lyrics.value = data
        loadedFor.value = id
        last = { id, data }
      } catch {
        // 下一次轮询再试
      }
    },
    { immediate: true },
  )

  const offset = computed(() => lyrics.value?.offset ?? 0)
  /** 能跟着播放走的歌词行;没有就是空数组 */
  const lines = computed(() => {
    const l = lyrics.value
    const ls = l?.lines ?? []
    return ls.length && (l?.aligned || offset.value !== 0) ? ls : []
  })

  /** 当前行:歌词时间 <= 播放位置 - 偏移 的最后一行(提前 0.2 秒,和 LyricsPanel 一致);第一行之前是 -1 */
  const active = computed(() => {
    const ls = lines.value
    if (!ls.length) return -1
    const at = clock.playhead - offset.value + 0.2
    let lo = 0
    let hi = ls.length - 1
    let found = -1
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      if (ls[mid]![0] <= at) { found = mid; lo = mid + 1 } else hi = mid - 1
    }
    return found
  })

  return { lines, active }
}
