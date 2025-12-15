<template>
  <div class="dashboard">
    <!-- Token Setup Dialog -->
    <el-dialog v-model="showTokenDialog" title="设置 API Token" width="400px" :close-on-click-modal="false">
      <el-form>
        <el-form-item label="API Token">
          <el-input v-model="tokenInput" placeholder="请输入 .env 中配置的 API_TOKEN" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="saveToken">保存</el-button>
      </template>
    </el-dialog>

    <!-- Stats Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
            <el-icon :size="28"><Monitor /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.channels }}</div>
            <div class="stat-label">活跃频道</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%)">
            <el-icon :size="28"><Folder /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.groups }}</div>
            <div class="stat-label">频道分组</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)">
            <el-icon :size="28"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.slots }} <small>({{ stats.enabledSlots }} 启用)</small></div>
            <div class="stat-label">广告槽位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)">
            <el-icon :size="28"><Picture /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.creatives }}</div>
            <div class="stat-label">广告素材</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Quick Actions -->
    <el-row :gutter="20" class="section">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/groups')">
              <el-icon><Plus /></el-icon>
              创建分组
            </el-button>
            <el-button type="success" @click="$router.push('/slots')">
              <el-icon><Plus /></el-icon>
              创建槽位
            </el-button>
            <el-button type="warning" @click="$router.push('/creatives')">
              <el-icon><Picture /></el-icon>
              管理素材
            </el-button>
            <el-button @click="showTokenDialog = true">
              <el-icon><Setting /></el-icon>
              设置 Token
            </el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>使用说明</span>
            </div>
          </template>
          <el-steps direction="vertical" :active="activeStep">
            <el-step title="添加 Bot 到频道" description="将 Bot 添加为频道管理员" />
            <el-step title="创建分组" description="在分组管理中创建频道分组" />
            <el-step title="创建槽位" description="为分组创建广告槽位并设置 Cron" />
            <el-step title="保存素材" description="私聊 Bot 发送消息保存为素材" />
            <el-step title="绑定素材" description="将素材绑定到槽位" />
          </el-steps>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Channels -->
    <el-card class="section">
      <template #header>
        <div class="card-header">
          <span>最近加入的频道</span>
          <el-button type="primary" link @click="$router.push('/channels')">查看全部</el-button>
        </div>
      </template>
      <el-table :data="recentChannels" style="width: 100%" v-loading="loading">
        <el-table-column prop="title" label="频道名称" />
        <el-table-column prop="tg_chat_id" label="Chat ID" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '已离开' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="permissions_ok" label="权限" width="100">
          <template #default="{ row }">
            <el-tag :type="row.permissions_ok ? 'success' : 'warning'" size="small">
              {{ row.permissions_ok ? '正常' : '不足' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && recentChannels.length === 0" description="暂无频道，请先将 Bot 添加到频道" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getChannels, getGroups, getSlots, getCreatives, setApiToken } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const showTokenDialog = ref(false)
const tokenInput = ref(localStorage.getItem('apiToken') || '')
const activeStep = ref(0)

const stats = ref({
  channels: 0,
  groups: 0,
  slots: 0,
  enabledSlots: 0,
  creatives: 0
})

const recentChannels = ref([])

const saveToken = () => {
  setApiToken(tokenInput.value)
  showTokenDialog.value = false
  ElMessage.success('Token 已保存')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const [channels, groups, slots, creatives] = await Promise.all([
      getChannels().catch(() => []),
      getGroups().catch(() => []),
      getSlots().catch(() => []),
      getCreatives().catch(() => [])
    ])

    stats.value.channels = channels.filter(c => c.status === 'active').length
    stats.value.groups = groups.length
    stats.value.slots = slots.length
    stats.value.enabledSlots = slots.filter(s => s.enabled).length
    stats.value.creatives = creatives.length

    recentChannels.value = channels.slice(0, 5)

    // Calculate active step
    if (channels.length === 0) activeStep.value = 0
    else if (groups.length === 0) activeStep.value = 1
    else if (slots.length === 0) activeStep.value = 2
    else if (creatives.length === 0) activeStep.value = 3
    else activeStep.value = 5
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!localStorage.getItem('apiToken')) {
    showTokenDialog.value = true
  }
  fetchData()
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 15px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-right: 15px;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-value small {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.section {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
