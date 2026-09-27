import { apiGet, apiPost } from './client'
import type { CurrentUser } from '../types'

export function login(
  username: string,
  password: string,
): Promise<{ ok: boolean; user: string; username: string; default_route?: string }> {
  return apiPost('/api/auth/login', { username, password })
}

export function logout(): Promise<{ ok: boolean }> {
  return apiPost('/api/auth/logout')
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiGet<CurrentUser>('/api/auth/me')
}

/**
 * 获取企业微信扫码登录 URL。
 * 前端拿到 url 后用 window.location.href 跳转过去，用户扫码后企微回调后端，
 * 后端重定向回前端首页并种 cookie，整个流程不需要前端处理 token。
 *
 * 后端未配置企业微信时返回 503，前端应隐藏"企业微信登录"按钮。
 */
export function getWecomQrcodeUrl(): Promise<{ url: string }> {
  return apiGet<{ url: string }>('/api/auth/wecom/qrcode')
}

/**
 * 获取企业微信静默授权 URL（snsapi_base）。
 * 用户从企微客户端内打开此 URL 时自动带上 code 回调，无需扫码。
 * 适用于工作台应用入口免登场景：前端检测到在企微内置浏览器中且未登录时，
 * 调用此接口获取 URL 并跳转，实现无感登录。
 */
export function getWecomSilentAuthUrl(): Promise<{ url: string }> {
  return apiGet<{ url: string }>('/api/auth/wecom/silent-auth')
}

/**
 * 企微自助绑定：用户扫码后未绑定，输入账号密码验证身份后绑定企微 userid。
 * 绑定成功后后端通过 Set-Cookie 设置会话，前端直接跳转首页即可。
 */
export function bindWecomAccount(
  wecomUserid: string,
  username: string,
  password: string,
): Promise<{ ok: boolean; user: string }> {
  return apiPost('/api/auth/wecom/bind', { wecom_userid: wecomUserid, username, password })
}
