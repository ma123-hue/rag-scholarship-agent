import { defineStore } from 'pinia'


export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('scholar_token') || '',
    username: localStorage.getItem('scholar_username') || '',
    isAdmin: localStorage.getItem('scholar_is_admin') === 'true',
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    setAuth(token, username, isAdmin) {
      this.token = token
      this.username = username
      this.isAdmin = Boolean(isAdmin)
      localStorage.setItem('scholar_token', token)
      localStorage.setItem('scholar_username', username)
      localStorage.setItem('scholar_is_admin', String(Boolean(isAdmin)))
    },
    logout() {
      this.token = ''
      this.username = ''
      this.isAdmin = false
      localStorage.removeItem('scholar_token')
      localStorage.removeItem('scholar_username')
      localStorage.removeItem('scholar_is_admin')
    },
  },
})
