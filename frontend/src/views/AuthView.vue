<script setup>
import { UserFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { login, loginAsDemoAdmin, register } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const activeTab = ref('login')
const loading = ref(false)
const demoMode = import.meta.env.VITE_DEMO_MODE === 'true'

const loginForm = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  password: '',
})

async function handleLogin() {
  loading.value = true
  try {
    const { data } = await login(loginForm)
    authStore.setAuth(data.access_token, data.username, data.is_admin)
    ElMessage.success('登录成功')
    await router.push('/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  loading.value = true
  try {
    const { data } = await register(registerForm)
    authStore.setAuth(data.access_token, data.username, data.is_admin)
    ElMessage.success('注册成功')
    await router.push('/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '注册失败')
  } finally {
    loading.value = false
  }
}

async function enterDemo() {
  loginForm.username = '招聘体验官'
  loginForm.password = 'demo-only'
  await handleLogin()
}

async function enterAdminDemo() {
  loading.value = true
  try {
    const { data } = await loginAsDemoAdmin()
    authStore.setAuth(data.access_token, data.username, data.is_admin)
    ElMessage.success('已进入管理端产品演示')
    await router.push('/admin/files')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-backdrop"></div>
    <section class="auth-copy">
      <span class="eyebrow">Scholarship Policy Intelligence</span>
      <h1>把复杂政策，变成可执行的申请判断。</h1>
      <p>
        输入你的学业表现、家庭情况和获奖经历，系统会检索本校政策条款，
        给出可申报项目、条件差距和下一步材料建议。
      </p>
    </section>

    <section class="auth-card">
      <div class="auth-header">
        <el-icon><UserFilled /></el-icon>
        <span>账户入口</span>
      </div>

      <div v-if="demoMode" class="demo-notice">
        <strong>免费产品演示</strong>
        <span>真实政策规则在浏览器本地计算，不调用模型、不上传数据。</span>
      </div>

      <div v-if="demoMode" class="demo-entry-group">
        <el-button class="demo-entry" type="primary" round :loading="loading" @click="enterDemo">
          体验用户端
        </el-button>
        <el-button class="demo-entry" type="success" plain round :loading="loading" @click="enterAdminDemo">
          体验管理端
        </el-button>
      </div>

      <div v-if="demoMode" class="demo-divider"><span>或体验账户流程</span></div>

      <el-tabs v-model="activeTab" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form label-position="top" @submit.prevent="handleLogin">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="输入用户名" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="输入密码" />
            </el-form-item>
            <el-button class="auth-submit" type="primary" round :loading="loading" @click="handleLogin">
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form label-position="top" @submit.prevent="handleRegister">
            <el-form-item label="用户名">
              <el-input v-model="registerForm.username" placeholder="至少 3 个字符" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="registerForm.password" type="password" show-password placeholder="至少 6 位密码" />
            </el-form-item>
            <el-button class="auth-submit" type="primary" round :loading="loading" @click="handleRegister">
              注册并进入
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </section>
  </div>
</template>
