// 当前标签页选中的服务器(guild)。存在 sessionStorage:每个标签页可以看不同的服务器,
// 刷新页面不丢。所有 API 请求都带 X-DJ-Guild 请求头(见 api.ts 的 apiFetch),
// 后端按它选会话;没选(空串)时后端用默认服务器。
import { ref, watch } from 'vue'

const STORAGE_KEY = 'djGuild'
export const GUILD_HEADER = 'X-DJ-Guild'

function load(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return '' // 隐私模式等读不到 sessionStorage
  }
}

export const selectedGuild = ref<string>(load())

watch(selectedGuild, (id) => {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch { /* ignore */ }
})

/** 合并进 fetch 的 headers */
export function guildHeaders(): Record<string, string> {
  return selectedGuild.value ? { [GUILD_HEADER]: selectedGuild.value } : {}
}
