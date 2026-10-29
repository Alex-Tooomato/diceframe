import { ref } from 'vue'
import { api } from '@/api/client'

/**
 * 当前登录角色：owner（管理面全权）或 builder（建房口令，只玩不管）。
 *
 * 后端在 /api/login 与 /api/me 里返回 role；这里缓存一份到
 * localStorage，让导航在探针完成前就能用上次的角色先渲染，
 * 探针结果回来后自动纠正。真正的权限边界在后端中间件，前端
 * 只负责不展示进不去的入口。
 */
export type AuthRole = 'owner' | 'builder' | ''

const STORAGE_KEY = 'trpg_auth_role'

export const authRole = ref<AuthRole>('')
export const authRoleLoaded = ref(false)

export function readStoredAuthRole(): AuthRole {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'builder' || value === 'owner' ? value : ''
  } catch {
    return ''
  }
}

export function writeStoredAuthRole(role: AuthRole) {
  try {
    if (role) localStorage.setItem(STORAGE_KEY, role)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* 隐私模式下 localStorage 可能不可用，忽略即可。 */
  }
}

let probe: Promise<AuthRole> | null = null

export function loadAuthRole(force = false): Promise<AuthRole> {
  if (!authRole.value) authRole.value = readStoredAuthRole()
  if (authRoleLoaded.value && !force) return Promise.resolve(authRole.value)
  if (!probe) {
    probe = (async () => {
      try {
        const me = await api<{ role?: string }>('/me')
        authRole.value = me.role === 'builder' ? 'builder' : 'owner'
      } catch {
        // 未登录或服务器不可达：保留本地缓存（可能为空），由路由守卫处理。
      } finally {
        authRoleLoaded.value = true
        writeStoredAuthRole(authRole.value)
        probe = null
      }
      return authRole.value
    })()
  }
  return probe
}

export function isBuilderRole(): boolean {
  return authRole.value === 'builder'
}
