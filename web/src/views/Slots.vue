<template>
  <div class="slots-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>槽位列表</span>
            <el-select
              v-model="filterGroupId"
              placeholder="筛选分组"
              clearable
              style="margin-left: 20px; width: 200px"
              @change="fetchSlots"
            >
              <el-option
                v-for="group in groups"
                :key="group.id"
                :label="group.name"
                :value="group.id"
              />
            </el-select>
          </div>
          <el-button type="primary" @click="showCreateDialog" :disabled="groups.length === 0">
            <el-icon><Plus /></el-icon>
            创建槽位
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="groups.length === 0"
        title="请先创建分组"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <el-table :data="slots" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="分组" width="150">
          <template #default="{ row }">
            {{ getGroupName(row.group_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="slot_index" label="序号" width="80" />
        <el-table-column prop="slot_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.slot_type === 'fixed' ? 'primary' : 'warning'" size="small">
              {{ row.slot_type === 'fixed' ? '固定' : '随机' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="publish_cron" label="发布 Cron" min-width="150">
          <template #default="{ row }">
            <el-tooltip :content="describeCron(row.publish_cron)">
              <code>{{ row.publish_cron }}</code>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="delete_mode" label="删除策略" width="120">
          <template #default="{ row }">
            <span v-if="row.delete_mode === 'none'">下次轮换</span>
            <span v-else-if="row.delete_mode === 'after_seconds'">
              {{ row.delete_after_seconds }}秒后
            </span>
            <span v-else-if="row.delete_mode === 'cron'">
              <code>{{ row.delete_cron }}</code>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              @change="toggleSlot(row)"
              :loading="row._toggling"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定要删除此槽位吗？"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && slots.length === 0" description="暂无槽位" />
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingSlot ? '编辑槽位' : '创建槽位'" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="所属分组" required>
          <el-select v-model="form.group_id" placeholder="选择分组" :disabled="!!editingSlot" style="width: 100%">
            <el-option
              v-for="group in groups"
              :key="group.id"
              :label="group.name"
              :value="group.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="槽位序号" required>
          <el-input-number v-model="form.slot_index" :min="1" :max="99" :disabled="!!editingSlot" />
          <span style="margin-left: 10px; color: #909399;">同一分组内不能重复</span>
        </el-form-item>
        <el-form-item label="槽位类型" required>
          <el-radio-group v-model="form.slot_type">
            <el-radio value="fixed">固定（单个素材）</el-radio>
            <el-radio value="random">随机（多个素材轮换）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="发布 Cron" required>
          <el-input v-model="form.publish_cron" placeholder="分 时 日 月 周，例如: 0 9 * * *" />
          <div style="font-size: 12px; color: #909399; margin-top: 5px;">
            格式：分 时 日 月 周（北京时间）<br>
            例如：<code>0 9 * * *</code> = 每天 9:00，<code>0 */2 * * *</code> = 每 2 小时
          </div>
        </el-form-item>
        <el-form-item label="删除策略">
          <el-radio-group v-model="form.delete_mode">
            <el-radio value="none">下次轮换时删除</el-radio>
            <el-radio value="after_seconds">延迟删除</el-radio>
            <el-radio value="cron">定时删除</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.delete_mode === 'after_seconds'" label="延迟秒数">
          <el-input-number v-model="form.delete_after_seconds" :min="60" :max="86400" :step="60" />
          <span style="margin-left: 10px; color: #909399;">
            {{ formatSeconds(form.delete_after_seconds) }}
          </span>
        </el-form-item>
        <el-form-item v-if="form.delete_mode === 'cron'" label="删除 Cron">
          <el-input v-model="form.delete_cron" placeholder="分 时 日 月 周" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ editingSlot ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getGroups, getSlots, createSlot, updateSlot, deleteSlot, enableSlot, disableSlot } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const groups = ref([])
const slots = ref([])
const filterGroupId = ref(null)

// Dialog
const dialogVisible = ref(false)
const editingSlot = ref(null)
const form = ref({
  group_id: null,
  slot_index: 1,
  slot_type: 'fixed',
  publish_cron: '0 9 * * *',
  delete_mode: 'none',
  delete_cron: '',
  delete_after_seconds: 3600
})

const getGroupName = (groupId) => {
  const group = groups.value.find(g => g.id === groupId)
  return group ? group.name : '未知'
}

const describeCron = (cron) => {
  // Simple cron description
  const parts = cron.split(' ')
  if (parts.length !== 5) return cron
  const [min, hour, day, month, dow] = parts
  if (day === '*' && month === '*' && dow === '*') {
    if (hour.startsWith('*/')) {
      return `每 ${hour.slice(2)} 小时的第 ${min} 分钟`
    }
    return `每天 ${hour}:${min.padStart(2, '0')}`
  }
  return cron
}

const formatSeconds = (seconds) => {
  if (!seconds) return ''
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  return `${(seconds / 3600).toFixed(1)} 小时`
}

const fetchGroups = async () => {
  try {
    groups.value = await getGroups()
  } catch (e) {
    console.error(e)
  }
}

const fetchSlots = async () => {
  loading.value = true
  try {
    slots.value = await getSlots(filterGroupId.value)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  editingSlot.value = null
  form.value = {
    group_id: filterGroupId.value || (groups.value[0]?.id || null),
    slot_index: 1,
    slot_type: 'fixed',
    publish_cron: '0 9 * * *',
    delete_mode: 'none',
    delete_cron: '',
    delete_after_seconds: 3600
  }
  dialogVisible.value = true
}

const showEditDialog = (slot) => {
  editingSlot.value = slot
  form.value = {
    group_id: slot.group_id,
    slot_index: slot.slot_index,
    slot_type: slot.slot_type,
    publish_cron: slot.publish_cron,
    delete_mode: slot.delete_mode,
    delete_cron: slot.delete_cron || '',
    delete_after_seconds: slot.delete_after_seconds || 3600
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.value.group_id) {
    ElMessage.warning('请选择分组')
    return
  }
  if (!form.value.publish_cron) {
    ElMessage.warning('请输入发布 Cron')
    return
  }

  submitting.value = true
  try {
    const data = {
      ...form.value,
      delete_cron: form.value.delete_mode === 'cron' ? form.value.delete_cron : null,
      delete_after_seconds: form.value.delete_mode === 'after_seconds' ? form.value.delete_after_seconds : null
    }

    if (editingSlot.value) {
      await updateSlot(editingSlot.value.id, data)
      ElMessage.success('槽位已更新')
    } else {
      await createSlot(data)
      ElMessage.success('槽位已创建')
    }
    dialogVisible.value = false
    fetchSlots()
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

const toggleSlot = async (slot) => {
  slot._toggling = true
  try {
    if (slot.enabled) {
      await enableSlot(slot.id)
      ElMessage.success('槽位已启用')
    } else {
      await disableSlot(slot.id)
      ElMessage.success('槽位已暂停')
    }
  } catch (e) {
    slot.enabled = !slot.enabled
    console.error(e)
  } finally {
    slot._toggling = false
  }
}

const handleDelete = async (id) => {
  try {
    await deleteSlot(id)
    ElMessage.success('槽位已删除')
    fetchSlots()
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  fetchGroups()
  fetchSlots()
})
</script>

<style scoped>
.slots-page {
  max-width: 1400px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
}

code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}
</style>
