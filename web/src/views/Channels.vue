<template>
  <div class="channels-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>频道列表</span>
          <el-button type="primary" @click="fetchChannels" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-alert
        title="提示：将 Bot 添加到频道并设为管理员后，频道会自动出现在这里"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <el-table :data="channels" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="频道名称" min-width="200">
          <template #default="{ row }">
            <div>
              <div>{{ row.title }}</div>
              <div v-if="row.username" style="font-size: 12px; color: #909399;">
                @{{ row.username }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="tg_chat_id" label="Chat ID" width="180">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.tg_chat_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '已离开' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="permissions_ok" label="权限" width="100">
          <template #default="{ row }">
            <el-tooltip :content="row.permissions_ok ? 'Bot 是管理员' : 'Bot 不是管理员，功能受限'">
              <el-tag :type="row.permissions_ok ? 'success' : 'warning'" size="small">
                {{ row.permissions_ok ? '正常' : '不足' }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定要移除此频道吗？"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button type="danger" link size="small">移除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && channels.length === 0" description="暂无频道">
        <template #default>
          <div style="color: #909399; font-size: 14px;">
            请将 Bot 添加到频道并设为管理员
          </div>
        </template>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getChannels, deleTGChannel } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const channels = ref([])

const fetchChannels = async () => {
  loading.value = true
  try {
    channels.value = await getChannels()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleDelete = async (id) => {
  try {
    await deleTGChannel(id)
    ElMessage.success('频道已移除')
    fetchChannels()
  } catch (e) {
    console.error(e)
  }
}

onMounted(fetchChannels)
</script>

<style scoped>
.channels-page {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
