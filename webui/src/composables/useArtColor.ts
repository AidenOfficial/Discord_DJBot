// 从专辑封面取色,生成一组配色(Material You / Monet 的算法:Google 的 material-color-utilities)。
// 1. 封面缩到 112×112 画进 canvas 读像素(Activity 里是 blob: 地址,网页版是同源地址,都不会被跨域污染);
// 2. QuantizerCelebi 量化成最多 128 种代表色,Score 按 Monet 的规则挑最适合当主题色的那个;
// 3. SchemeContent(忠实还原内容色的方案)从它生成整套色阶,取 primaryContainer 当底色、
//    onPrimaryContainer 当文字 —— 色阶本身保证两者的对比度。
// 黑白封面挑不出够鲜艳的颜色时,Monet 会退回谷歌蓝,和封面毫不相干:这里改用不过滤低彩度的结果,得到一组灰调。
import { Hct, QuantizerCelebi, SchemeContent, Score, argbFromRgb, hexFromArgb } from '@material/material-color-utilities'

export interface ArtPalette {
  /** 底色 */
  bg: string
  /** 正文 */
  fg: string
  /** 强调(进度条等) */
  accent: string
}

const SIZE = 112
const NO_COLOR = 0
// 同一张图不重复算(换回上一首、小窗反复开合)
const cache = new Map<string, number>()

/** 封面的主题色(ARGB);读不到像素就是 null */
export function sourceColorOf(img: HTMLImageElement, key: string): number | null {
  const hit = cache.get(key)
  if (hit !== undefined) return hit
  try {
    const canvas = document.createElement('canvas')
    canvas.width = SIZE
    canvas.height = SIZE
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(img, 0, 0, SIZE, SIZE)
    const { data } = ctx.getImageData(0, 0, SIZE, SIZE)
    const pixels: number[] = []
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3]! < 255) continue
      pixels.push(argbFromRgb(data[i]!, data[i + 1]!, data[i + 2]!))
    }
    if (!pixels.length) return null
    const colors = QuantizerCelebi.quantize(pixels, 128)
    let source = Score.score(colors, { desired: 1, fallbackColorARGB: NO_COLOR })[0] ?? NO_COLOR
    if (source === NO_COLOR) source = Score.score(colors, { desired: 1, filter: false })[0] ?? NO_COLOR
    if (source === NO_COLOR) return null
    cache.set(key, source)
    return source
  } catch {
    // canvas 被污染或者解码失败:不取色,用默认的强调色
    return null
  }
}

export function paletteFor(source: number, dark: boolean): ArtPalette {
  const scheme = new SchemeContent(Hct.fromInt(source), dark, 0)
  return {
    bg: hexFromArgb(scheme.primaryContainer),
    fg: hexFromArgb(scheme.onPrimaryContainer),
    accent: hexFromArgb(scheme.primary),
  }
}

/** 页面现在是不是深色(和 App 的主题逻辑一致:固定的 data-theme 优先,否则跟系统 / iOS Activity 的默认深色) */
export function renderedDark(): boolean {
  const root = document.documentElement
  const pinned = root.getAttribute('data-theme')
  if (pinned === 'dark' || pinned === 'light') return pinned === 'dark'
  if (root.getAttribute('data-theme-default') === 'dark') return true
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
}
