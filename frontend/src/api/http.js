import axios from 'axios'

import router from '../router'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('scholar_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('scholar_token')
      localStorage.removeItem('scholar_username')
      if (router.currentRoute.value.path !== '/login') {
        await router.push('/login')
      }
    }
    return Promise.reject(error)
  },
)

export default http
