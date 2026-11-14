// Metro 正在播放页的跳转状态。进度条在不同版面里出现在不同位置(信息磁贴里 / 手机版单独一行),
// 歌词也要预览拖动中的位置,所以拖动目标和"刚跳转过"放在模块里共享,不跟着某个组件实例走。
// 逻辑和 components/NowPlaying.vue 一致。
import { computed, effectScope, ref, watch } from 'vue'
import { postControls } from '../api'
import { useStatus } from '../composables/useStatus'

/** 拖动 / 键盘调整中的目标位置(秒);null = 没在调整 */
const dragAt = ref<number | null>(null)
/** 刚跳转:ffmpeg 重新打开文件的那几秒不显示准备面板 */
const seekingSince = ref(0)
let keyTimer: ReturnType<typeof setTimeout> | undefined
let wired = false

export function useSeek() {
  const { status, clock, applyStatus } = useStatus()
  if (!wired) {
    wired = true
    // 不挂在任何组件上:组件卸载再挂载时不会重复注册
    effectScope(true).run(() => {
      watch(() => status.value?.prep, (prep) => {
        if (!prep) seekingSince.value = 0
      })
      watch(() => status.value?.current?.id, () => {
        dragAt.value = null
        seekingSince.value = 0
      })
    })
  }

  const duration = computed(() => status.value?.current?.duration || 0)
  const canSeek = computed(() => duration.value > 0)
  const shownPlayhead = computed(() => dragAt.value ?? clock.playhead)

  function clampSeek(seconds: number) {
    return Math.min(Math.max(0, duration.value - 1), Math.max(0, seconds))
  }

  async function seek(position: number) {
    clearTimeout(keyTimer)
    seekingSince.value = performance.now()
    clock.playhead = position
    try {
      applyStatus(await postControls({ action: 'seek', position }))
    } catch {
      // 直播 / 已经切歌:下一次轮询会带回真实位置
    } finally {
      dragAt.value = null
    }
  }

  /** 键盘和读屏手势:先只移动预览位置,停手 0.4 秒再真正跳转(每次跳转都要重启 ffmpeg) */
  function scheduleSeek(target: number) {
    dragAt.value = target
    clearTimeout(keyTimer)
    keyTimer = setTimeout(() => {
      if (dragAt.value !== null) void seek(dragAt.value)
    }, 400)
  }

  const showPrep = computed(() => {
    if (!status.value?.current || !status.value.prep) return false
    // 跳转后几秒内的"准备中"只是 ffmpeg 在重新打开文件,别把进度条换成准备面板
    return !seekingSince.value || performance.now() - seekingSince.value > 4000
  })

  return { dragAt, duration, canSeek, shownPlayhead, clampSeek, seek, scheduleSeek, showPrep }
}
