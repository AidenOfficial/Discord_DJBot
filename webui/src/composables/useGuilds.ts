import { computed, ref } from 'vue'
import { fetchGuilds, type GuildInfo } from '../api'
import { selectedGuild } from '../guild'

// 模块级单例:顶栏的服务器切换、设置页的管理区、统计页的筛选共用。
const guilds = ref<GuildInfo[]>([])
const owner = ref(false)
const multi = ref(false)
const loaded = ref(false)
let started = false

async function reloadGuilds() {
  try {
    const data = await fetchGuilds()
    guilds.value = data.guilds
    owner.value = data.owner
    multi.value = data.multi
    // 这个标签页记着的服务器不能用了(权限变了 / bot 离开了):换成后端选的默认服务器
    const ids = data.guilds.map((g) => g.id)
    if (!ids.includes(selectedGuild.value)) {
      selectedGuild.value = data.guilds.find((g) => g.selected)?.id ?? ids[0] ?? ''
    }
  } catch {
    /* 状态轮询那边会提示连接错误 */
  } finally {
    loaded.value = true
  }
}

function selectGuild(id: string) {
  if (id !== selectedGuild.value) selectedGuild.value = id
}

const currentGuild = computed(() => guilds.value.find((g) => g.id === selectedGuild.value) ?? null)
/** 能改当前服务器的设置 */
const canManage = computed(() => !!currentGuild.value?.can_manage)
/** 多服务器模式下一个服务器都不能操作(没绑定 Discord / 没用 Discord 登录) */
const noAccess = computed(() => loaded.value && multi.value && guilds.value.length === 0)

export function useGuilds() {
  if (!started) {
    started = true
    reloadGuilds()
  }
  return { guilds, owner, multi, loaded, selectedGuild, currentGuild, canManage, noAccess, reloadGuilds, selectGuild }
}
