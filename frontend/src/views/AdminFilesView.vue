<script setup>
import { ArrowLeft, Delete, FolderAdd, RefreshRight, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { deletePolicyFile, fetchPolicyFiles, rebuildKnowledgeBase, uploadPolicyFile } from '../api/admin'
import { formatApiDate } from '../utils/time'

const router = useRouter()
const files = ref([])
const loading = ref(false)
const rebuilding = ref(false)
const uploading = ref(false)

function formatSize(size) {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function formatTime(value) {
  return formatApiDate(value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadFiles() {
  loading.value = true
  try {
    const { data } = await fetchPolicyFiles()
    files.value = data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '加载文件失败')
  } finally {
    loading.value = false
  }
}

async function handleFileChange(uploadFile) {
  uploading.value = true
  try {
    await uploadPolicyFile(uploadFile.raw)
    ElMessage.success('文件上传成功')
    await loadFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '文件上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleDelete(file) {
  try {
    await ElMessageBox.confirm(`确认删除文件「${file.original_filename}」吗？`, '删除文件', {
      type: 'warning',
    })
    await deletePolicyFile(file.id)
    ElMessage.success('文件已删除')
    await loadFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || error.message || '删除失败')
    }
  }
}

async function handleRebuild() {
  rebuilding.value = true
  try {
    const { data } = await rebuildKnowledgeBase()
    ElMessage.success(`知识库重建完成：${data.document_count} 个文档，${data.chunk_count} 个切片`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '重建失败')
  } finally {
    rebuilding.value = false
  }
}

async function goBack() {
  await router.push('/')
}

onMounted(() => {
  loadFiles()
})
</script>

<template>
  <div class="admin-page">
    <section class="admin-shell">
      <header class="admin-header">
        <div>
          <p class="chat-kicker">管理员控制台</p>
          <h2>政策文件管理</h2>
          <p class="admin-copy">上传、删除政策文件，并在变更后手动重建知识库。</p>
        </div>
        <div class="admin-actions">
          <el-button round @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            返回对话
          </el-button>
          <el-upload
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleFileChange"
            accept=".pdf,.docx,.txt"
          >
            <el-button type="primary" round :loading="uploading">
              <el-icon><Upload /></el-icon>
              上传文件
            </el-button>
          </el-upload>
          <el-button type="success" round :loading="rebuilding" @click="handleRebuild">
            <el-icon><RefreshRight /></el-icon>
            重建知识库
          </el-button>
        </div>
      </header>

      <section class="admin-card">
        <div class="admin-card-head">
          <div class="admin-card-title">
            <el-icon><FolderAdd /></el-icon>
            <span>已管理文件</span>
          </div>
          <span class="admin-card-meta">{{ files.length }} 个文件</span>
        </div>

        <el-table v-loading="loading" :data="files" stripe>
          <el-table-column prop="original_filename" label="原始文件名" min-width="260" />
          <el-table-column prop="file_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.file_type.toUpperCase() }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">
              {{ formatSize(row.size_bytes) }}
            </template>
          </el-table-column>
          <el-table-column prop="uploaded_by" label="上传人" width="140" />
          <el-table-column label="上传时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button type="danger" text @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </section>
  </div>
</template>
