<template>
  <div class="groups-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>分组列表</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            创建分组
          </el-button>
        </div>
      </template>

      <el-table :data="groups" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="分组名称" min-width="200" />
        <el-table-column prop="default_slot_count" label="默认槽位数" width="120" />
        <el-table-column prop="channel_count" label="频道数" width="100">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.channel_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showChannelsDialog(row)">
              管理频道
            </el-button>
            <el-button type="warning" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定要删除此分组吗？关联的槽位也会被删除"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && groups.length === 0" description="暂无分组">
        <el-button type="primary" @click="showCreateDialog">创建第一个分组</el-button>
      </el-empty>
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingGroup ? '编辑分组' : '创建分组'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="分组名称" required>
          <el-input v-model="form.name" placeholder="请输入分组名称" />
        </el-form-item>
        <el-form-item label="默认槽位数">
          <el-input-number v-model="form.default_slot_count" :min="1" :max="20" />
          <div style="font-size: 12px; color: #909399; margin-top: 5px;">
            创建槽位时的默认数量
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ editingGroup ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Channels Dialog -->
    <el-dialog v-model="channelsDialogVisible" title="管理分组频道" width="700px">
      <div v-if="selectedGroup">
        <el-alert
          :title="`当前分组：${selectedGroup.name}`"
          type="info"
          :closable="false"
          style="margin-bottom: 20px"
        />

        <h4 style="margin-bottom: 10px;">已添加的频道</h4>
        <el-table :data="groupChannels" style="width: 100%; margin-bottom: 20px" max-height="200">
          <el-table-column prop="title" label="频道名称" />
          <el-table-column prop="tg_chat_id" label="Chat ID" width="150" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="removeFromGroup(row.id)">
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="groupChannels.length === 0" description="暂未添加频道" :image-size="60" />

        <el-divider />

        <h4 style="margin-bottom: 10px;">添加频道到分组</h4>
        <el-select
          v-model="selectedChannelIds"
          multiple
          filterable
          placeholder="选择要添加的频道"
          style="width: 100%; margin-bottom: 10px"
        >
          <el-option
            v-for="channel in availableChannels"
            :key="channel.id"
            :label="channel.title"
            :value="channel.id"
          >
            <span>{{ channel.title }}</span>
            <span style="color: #909399; font-size: 12px; margin-left: 10px;">
              {{ channel.tg_chat_id }}
            </span>
          </el-option>
        </el-select>
        <el-button type="primary" @click="addToGroup" :disabled="selectedChannelIds.length === 0">
          添加选中的频道
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  getGroups, createGroup, updateGroup, deleteGroup,
  getChannels, getGroupChannels, addChannelsToGroup, removeChannelFromGroup
} from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const groups = ref([])
const allChannels = ref([])

// Create/Edit Dialog
const dialogVisible = ref(false)
const editingGroup = ref(null)
const form = ref({
  name: '',
  default_slot_count: 5
})

// Channels Dialog
const channelsDialogVisible = ref(false)
const selectedGroup = ref(null)
const groupChannels = ref([])
const selectedChannelIds = ref([])

const availableChannels = computed(() => {
  const groupChannelIds = new Set(groupChannels.value.map(c => c.id))
  return allChannels.value.filter(c => c.status === 'active' && !groupChannelIds.has(c.id))
})

const fetchGroups = async () => {
  loading.value = true
  try {
    groups.value = await getGroups()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchChannels = async () => {
  try {
    allChannels.value = await getChannels()
  } catch (e) {
    console.error(e)
  }
}

const showCreateDialog = () => {
  editingGroup.value = null
  form.value = { name: '', default_slot_count: 5 }
  dialogVisible.value = true
}

const showEditDialog = (group) => {
  editingGroup.value = group
  form.value = {
    name: group.name,
    default_slot_count: group.default_slot_count
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入分组名称')
    return
  }

  submitting.value = true
  try {
    if (editingGroup.value) {
      await updateGroup(editingGroup.value.id, form.value)
      ElMessage.success('分组已更新')
    } else {
      await createGroup(form.value)
      ElMessage.success('分组已创建')
    }
    dialogVisible.value = false
    fetchGroups()
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id) => {
  try {
    await deleteGroup(id)
    ElMessage.success('分组已删除')
    fetchGroups()
  } catch (e) {
    console.error(e)
  }
}

const showChannelsDialog = async (group) => {
  selectedGroup.value = group
  selectedChannelIds.value = []
  channelsDialogVisible.value = true

  try {
    groupChannels.value = await getGroupChannels(group.id)
  } catch (e) {
    groupChannels.value = []
  }
}

const addToGroup = async () => {
  if (selectedChannelIds.value.length === 0) return

  try {
    await addChannelsToGroup(selectedGroup.value.id, selectedChannelIds.value)
    ElMessage.success('频道已添加')
    selectedChannelIds.value = []
    groupChannels.value = await getGroupChannels(selectedGroup.value.id)
    fetchGroups()
  } catch (e) {
    console.error(e)
  }
}

const removeFromGroup = async (channelId) => {
  try {
    await removeChannelFromGroup(selectedGroup.value.id, channelId)
    ElMessage.success('频道已移除')
    groupChannels.value = await getGroupChannels(selectedGroup.value.id)
    fetchGroups()
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  fetchGroups()
  fetchChannels()
})
</script>

<style scoped>
.groups-page {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
