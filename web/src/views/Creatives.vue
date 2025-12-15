<template>
  <div class="creatives-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>素材列表</span>
            <el-select
              v-model="filterSlotId"
              placeholder="筛选槽位"
              clearable
              style="margin-left: 20px; width: 200px"
              @change="fetchCreatives"
            >
              <el-option label="未绑定" :value="-1" />
              <el-option
                v-for="slot in slots"
                :key="slot.id"
                :label="`${getGroupName(slot.group_id)} - 槽位 ${slot.slot_index}`"
                :value="slot.id"
              />
            </el-select>
          </div>
          <el-button @click="fetchCreatives" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-alert
        title="提示：私聊 Bot 发送消息即可保存为素材"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <el-table :data="creatives" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getMediaTagType(row.media_type)" size="small">
              {{ getMediaLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="caption_preview" label="内容预览" min-width="250">
          <template #default="{ row }">
            <span v-if="row.caption_preview">{{ row.caption_preview }}</span>
            <span v-else style="color: #909399;">(无文字)</span>
          </template>
        </el-table-column>
        <el-table-column label="绑定槽位" width="180">
          <template #default="{ row }">
            <template v-if="row.slot_id">
              <el-tag type="success" size="small">
                {{ getSlotLabel(row.slot_id) }}
              </el-tag>
            </template>
            <el-tag v-else type="info" size="small">未绑定</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="按钮" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.inline_keyboard_json" type="primary" size="small">
              有按钮
            </el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-button type="success" link size="small" @click="showBindDialog(row)">
              绑定
            </el-button>
            <el-button v-if="row.slot_id" type="warning" link size="small" @click="handleUnbind(row)">
              解绑
            </el-button>
            <el-popconfirm
              title="确定要删除此素材吗？"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && creatives.length === 0" description="暂无素材">
        <template #default>
          <div style="color: #909399; font-size: 14px;">
            私聊 Bot 发送消息保存为素材
          </div>
        </template>
      </el-empty>
    </el-card>

    <!-- Edit Dialog -->
    <el-dialog v-model="editDialogVisible" title="编辑素材" width="700px">
      <div v-if="editingCreative">
        <el-descriptions :column="2" border style="margin-bottom: 20px">
          <el-descriptions-item label="素材 ID">{{ editingCreative.id }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="getMediaTagType(editingCreative.media_type)" size="small">
              {{ getMediaLabel(editingCreative) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-form :model="editForm" label-width="100px">
          <el-form-item label="启用状态">
            <el-switch v-model="editForm.enabled" />
          </el-form-item>

          <el-divider content-position="left">
            <el-icon><Edit /></el-icon>
            内容编辑
          </el-divider>

          <el-form-item label="文字内容">
            <el-input
              v-model="editForm.caption"
              type="textarea"
              :rows="6"
              :placeholder="editingCreative.has_media ? '图片/视频的文字说明' : '消息文字内容'"
            />
            <div style="font-size: 12px; color: #909399; margin-top: 5px;">
              {{ editingCreative.has_media ? '媒体的 caption（可选）' : '纯文字消息内容' }}
            </div>
          </el-form-item>

          <el-divider content-position="left">
            <el-icon><Link /></el-icon>
            按钮配置
          </el-divider>

          <el-form-item label="编辑模式">
            <el-radio-group v-model="buttonEditMode">
              <el-radio value="simple">简单模式</el-radio>
              <el-radio value="advanced">高级模式 (JSON)</el-radio>
            </el-radio-group>
          </el-form-item>

          <!-- Simple Mode -->
          <el-form-item v-if="buttonEditMode === 'simple'" label="按钮配置">
            <div style="width: 100%;">
              <el-input
                v-model="simpleButtonText"
                type="textarea"
                :rows="6"
                placeholder="每行一个按钮，格式：按钮文字 | URL
同一行多个按钮用 | 分隔：按钮1 | URL1 | 按钮2 | URL2

示例：
官网 | https://example.com
联系我们 | https://t.me/xxx
购买 | https://buy.com | 咨询 | https://t.me/support"
                @input="parseSimpleButtons"
              />
              <div v-if="parseError" style="color: #f56c6c; font-size: 12px; margin-top: 5px;">
                {{ parseError }}
              </div>
            </div>
          </el-form-item>

          <!-- Advanced Mode -->
          <el-form-item v-if="buttonEditMode === 'advanced'" label="JSON 配置">
            <el-input
              v-model="advancedButtonJson"
              type="textarea"
              :rows="8"
              placeholder='[
  [{"text": "按钮1", "url": "https://..."}],
  [{"text": "按钮2", "url": "..."}, {"text": "按钮3", "url": "..."}]
]'
              @input="parseAdvancedButtons"
            />
            <div v-if="jsonParseError" style="color: #f56c6c; font-size: 12px; margin-top: 5px;">
              {{ jsonParseError }}
            </div>
          </el-form-item>

          <!-- Preview -->
          <el-form-item label="按钮预览">
            <div class="button-preview">
              <div v-if="parsedButtons.length === 0" class="no-buttons">
                暂无按钮
              </div>
              <div v-else class="preview-container">
                <div v-for="(row, rowIndex) in parsedButtons" :key="rowIndex" class="button-row">
                  <div
                    v-for="(btn, btnIndex) in row"
                    :key="btnIndex"
                    class="preview-button"
                    :style="{ width: `${100 / row.length - 2}%` }"
                  >
                    {{ btn.text }}
                  </div>
                </div>
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveEdit" :loading="submitting">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- Bind Dialog -->
    <el-dialog v-model="bindDialogVisible" title="绑定到槽位" width="500px">
      <div v-if="selectedCreative">
        <el-descriptions :column="1" border style="margin-bottom: 20px">
          <el-descriptions-item label="素材 ID">{{ selectedCreative.id }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ getMediaLabel(selectedCreative) }}</el-descriptions-item>
          <el-descriptions-item label="预览">
            {{ selectedCreative.caption_preview || '(无文字)' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-form label-width="80px">
          <el-form-item label="选择槽位">
            <el-select v-model="bindSlotId" placeholder="选择要绑定的槽位" style="width: 100%">
              <el-option-group
                v-for="group in groupedSlots"
                :key="group.group_id"
                :label="group.group_name"
              >
                <el-option
                  v-for="slot in group.slots"
                  :key="slot.id"
                  :label="`槽位 ${slot.slot_index} (${slot.slot_type === 'fixed' ? '固定' : '随机'})`"
                  :value="slot.id"
                />
              </el-option-group>
            </el-select>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="bindDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleBind" :disabled="!bindSlotId">
          绑定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import {
  getCreatives, getUnboundCreatives, deleteCreative, bindCreative, unbindCreative,
  getSlots, getGroups, updateCreative
} from '@/api'
import { ElMessage } from 'element-plus'
import { Link, Edit } from '@element-plus/icons-vue'

const loading = ref(false)
const submitting = ref(false)
const creatives = ref([])
const slots = ref([])
const groups = ref([])
const filterSlotId = ref(null)

// Bind Dialog
const bindDialogVisible = ref(false)
const selectedCreative = ref(null)
const bindSlotId = ref(null)

// Edit Dialog
const editDialogVisible = ref(false)
const editingCreative = ref(null)
const editForm = ref({
  enabled: true,
  caption: ''
})
const buttonEditMode = ref('simple')
const simpleButtonText = ref('')
const advancedButtonJson = ref('')
const parsedButtons = ref([])
const parseError = ref('')
const jsonParseError = ref('')

const groupedSlots = computed(() => {
  const result = []
  const groupMap = new Map()

  for (const slot of slots.value) {
    if (!groupMap.has(slot.group_id)) {
      const group = groups.value.find(g => g.id === slot.group_id)
      groupMap.set(slot.group_id, {
        group_id: slot.group_id,
        group_name: group?.name || '未知分组',
        slots: []
      })
    }
    groupMap.get(slot.group_id).slots.push(slot)
  }

  return Array.from(groupMap.values())
})

const getGroupName = (groupId) => {
  const group = groups.value.find(g => g.id === groupId)
  return group ? group.name : '未知'
}

const getSlotLabel = (slotId) => {
  const slot = slots.value.find(s => s.id === slotId)
  if (!slot) return '未知'
  return `${getGroupName(slot.group_id)} - 槽位 ${slot.slot_index}`
}

const getMediaLabel = (creative) => {
  if (!creative.has_media) return '文字'
  const labels = {
    photo: '图片',
    video: '视频',
    document: '文件',
    animation: 'GIF'
  }
  return labels[creative.media_type] || creative.media_type
}

const getMediaTagType = (mediaType) => {
  if (!mediaType) return 'info'
  const types = {
    photo: 'success',
    video: 'warning',
    document: '',
    animation: 'primary'
  }
  return types[mediaType] || 'info'
}

// Parse simple button format to JSON
const parseSimpleButtons = () => {
  parseError.value = ''
  const lines = simpleButtonText.value.trim().split('\n').filter(line => line.trim())

  if (lines.length === 0) {
    parsedButtons.value = []
    return
  }

  try {
    const result = []
    for (const line of lines) {
      if (line.trim() === '---') continue // Skip separator lines

      const parts = line.split('|').map(p => p.trim()).filter(p => p)
      if (parts.length < 2) {
        parseError.value = `格式错误: "${line}" - 需要 "按钮文字 | URL" 格式`
        return
      }

      if (parts.length % 2 !== 0) {
        parseError.value = `格式错误: "${line}" - 按钮和URL必须成对出现`
        return
      }

      const rowButtons = []
      for (let i = 0; i < parts.length; i += 2) {
        const text = parts[i]
        const url = parts[i + 1]

        if (!url.startsWith('http://') && !url.startsWith('https://') && !url.startsWith('tg://')) {
          parseError.value = `URL 格式错误: "${url}" - 必须以 http://, https:// 或 tg:// 开头`
          return
        }

        rowButtons.push({ text, url })
      }
      result.push(rowButtons)
    }
    parsedButtons.value = result
  } catch (e) {
    parseError.value = '解析错误: ' + e.message
  }
}

// Parse advanced JSON format
const parseAdvancedButtons = () => {
  jsonParseError.value = ''

  if (!advancedButtonJson.value.trim()) {
    parsedButtons.value = []
    return
  }

  try {
    const parsed = JSON.parse(advancedButtonJson.value)
    if (!Array.isArray(parsed)) {
      jsonParseError.value = 'JSON 必须是数组格式'
      return
    }

    // Validate structure
    for (const row of parsed) {
      if (!Array.isArray(row)) {
        jsonParseError.value = '每行必须是数组'
        return
      }
      for (const btn of row) {
        if (!btn.text || !btn.url) {
          jsonParseError.value = '每个按钮必须有 text 和 url 属性'
          return
        }
      }
    }

    parsedButtons.value = parsed
  } catch (e) {
    jsonParseError.value = 'JSON 解析错误: ' + e.message
  }
}

// Convert parsed buttons back to simple format
const buttonsToSimpleFormat = (buttons) => {
  if (!buttons || buttons.length === 0) return ''

  return buttons.map(row => {
    return row.map(btn => `${btn.text} | ${btn.url}`).join(' | ')
  }).join('\n')
}

// Convert parsed buttons to JSON string
const buttonsToJson = (buttons) => {
  if (!buttons || buttons.length === 0) return ''
  return JSON.stringify(buttons, null, 2)
}

const fetchCreatives = async () => {
  loading.value = true
  try {
    if (filterSlotId.value === -1) {
      creatives.value = await getUnboundCreatives()
    } else {
      creatives.value = await getCreatives(filterSlotId.value || null)
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchSlots = async () => {
  try {
    slots.value = await getSlots()
  } catch (e) {
    console.error(e)
  }
}

const fetchGroups = async () => {
  try {
    groups.value = await getGroups()
  } catch (e) {
    console.error(e)
  }
}

const showEditDialog = (creative) => {
  editingCreative.value = creative
  editForm.value = {
    enabled: creative.enabled,
    caption: creative.caption || ''
  }

  // Parse existing buttons
  if (creative.inline_keyboard_json) {
    try {
      const buttons = JSON.parse(creative.inline_keyboard_json)
      parsedButtons.value = buttons
      simpleButtonText.value = buttonsToSimpleFormat(buttons)
      advancedButtonJson.value = buttonsToJson(buttons)
    } catch (e) {
      parsedButtons.value = []
      simpleButtonText.value = ''
      advancedButtonJson.value = creative.inline_keyboard_json
      buttonEditMode.value = 'advanced'
    }
  } else {
    parsedButtons.value = []
    simpleButtonText.value = ''
    advancedButtonJson.value = ''
  }

  buttonEditMode.value = 'simple'
  parseError.value = ''
  jsonParseError.value = ''
  editDialogVisible.value = true
}

const handleSaveEdit = async () => {
  if (parseError.value || jsonParseError.value) {
    ElMessage.warning('请先修复按钮配置错误')
    return
  }

  submitting.value = true
  try {
    const data = {
      enabled: editForm.value.enabled,
      caption: editForm.value.caption || null,
      inline_keyboard_json: parsedButtons.value.length > 0
        ? JSON.stringify(parsedButtons.value)
        : null
    }

    await updateCreative(editingCreative.value.id, data)
    ElMessage.success('素材已更新')
    editDialogVisible.value = false
    fetchCreatives()
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

const showBindDialog = (creative) => {
  selectedCreative.value = creative
  bindSlotId.value = creative.slot_id
  bindDialogVisible.value = true
}

const handleBind = async () => {
  if (!bindSlotId.value) return

  try {
    await bindCreative(selectedCreative.value.id, bindSlotId.value)
    ElMessage.success('素材已绑定')
    bindDialogVisible.value = false
    fetchCreatives()
  } catch (e) {
    console.error(e)
  }
}

const handleUnbind = async (creative) => {
  try {
    await unbindCreative(creative.id)
    ElMessage.success('素材已解绑')
    fetchCreatives()
  } catch (e) {
    console.error(e)
  }
}

const handleDelete = async (id) => {
  try {
    await deleteCreative(id)
    ElMessage.success('素材已删除')
    fetchCreatives()
  } catch (e) {
    console.error(e)
  }
}

// Watch for mode changes to sync data
watch(buttonEditMode, (newMode) => {
  if (newMode === 'simple') {
    simpleButtonText.value = buttonsToSimpleFormat(parsedButtons.value)
    parseError.value = ''
  } else {
    advancedButtonJson.value = buttonsToJson(parsedButtons.value)
    jsonParseError.value = ''
  }
})

onMounted(() => {
  fetchCreatives()
  fetchSlots()
  fetchGroups()
})
</script>

<style scoped>
.creatives-page {
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

.button-preview {
  width: 100%;
  min-height: 80px;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  padding: 15px;
  background: #f5f7fa;
}

.no-buttons {
  text-align: center;
  color: #909399;
  line-height: 50px;
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.button-row {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.preview-button {
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 6px;
  text-align: center;
  font-size: 14px;
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
