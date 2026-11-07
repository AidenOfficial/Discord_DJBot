import { createApp } from 'vue'
import './style.css'
import ActivityGate from './ActivityGate.vue'
import { embedded } from './activity'
import { Icon } from './icons'

import { reportClientError } from './api'

// Discord Activity 里:样式按 iframe 调整(安全区、隐藏服务器切换等)
if (embedded) document.documentElement.classList.add('embedded')

const app = createApp(ActivityGate)
app.component('Icon', Icon)
// 组件里抛出的错误 + 全局未捕获错误都报给后端,在 设置 → 日志 里能看到
app.config.errorHandler = (err, _instance, info) => {
  console.error(err)
  const e = err instanceof Error ? err : new Error(String(err))
  reportClientError(`${e.name}: ${e.message} (vue: ${info})`, e.stack)
}
window.addEventListener('error', (ev) => {
  if (ev.error instanceof Error) reportClientError(`${ev.error.name}: ${ev.error.message}`, ev.error.stack)
  else if (ev.message) reportClientError(ev.message, `${ev.filename}:${ev.lineno}`)
})
window.addEventListener('unhandledrejection', (ev) => {
  const r = ev.reason
  reportClientError(`Unhandled rejection: ${r instanceof Error ? `${r.name}: ${r.message}` : String(r)}`,
    r instanceof Error ? r.stack : undefined)
})
app.mount('#app')
