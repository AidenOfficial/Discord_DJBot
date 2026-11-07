<script setup lang="ts">
// <img>,但 Activity 里图片请求带不了 Authorization 头:用 apiFetch 取成 blob 再显示。
// 普通网页里就是原样的 <img :src>。外部地址先经 imageSrc() 换成 /api/thumbnail/external。
// class、alt、loading、@load、@error 等都透传给 <img>;loading="lazy" 时等滚到附近才取。
import { onBeforeUnmount, onMounted, ref, useAttrs, watch } from 'vue'
import { embedded, imageSrc } from '../activity'
import { authedImage } from '../authedImage'

const props = defineProps<{ src: string | null | undefined }>()
const attrs = useAttrs()

const el = ref<HTMLImageElement | null>(null)
const shown = ref<string | undefined>(embedded ? undefined : imageSrc(props.src) || undefined)
let visible = !embedded || attrs.loading !== 'lazy'
let observer: IntersectionObserver | null = null
let wanted = ''

async function load() {
  const url = imageSrc(props.src)
  if (!embedded) {
    shown.value = url || undefined
    return
  }
  if (!url || url.startsWith('data:') || url.startsWith('blob:')) {
    shown.value = url || undefined
    return
  }
  if (!visible) return
  wanted = url
  const blobUrl = await authedImage(url)
  if (wanted !== url) return // 等的时候换图了
  // 取不到:给个无效地址让 <img> 触发 error 事件,和普通网页的行为一致
  shown.value = blobUrl ?? 'data:,'
}

watch(() => props.src, () => { void load() })

onMounted(() => {
  if (!visible && el.value && 'IntersectionObserver' in window) {
    observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        visible = true
        observer?.disconnect()
        observer = null
        void load()
      }
    }, { rootMargin: '200px' })
    observer.observe(el.value)
  } else {
    visible = true
  }
  void load()
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <img ref="el" :src="shown" />
</template>
