import http from './http'
import { demoAuth } from './demo'

const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'

export function login(payload) {
  if (demoMode) return demoAuth(payload.username)
  return http.post('/auth/login', payload)
}

export function register(payload) {
  if (demoMode) return demoAuth(payload.username)
  return http.post('/auth/register', payload)
}
