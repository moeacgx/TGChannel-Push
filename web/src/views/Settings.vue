<template>
  <div class="settings-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统设置</span>
        </div>
      </template>

      <el-form
        :model="form"
        label-width="140px"
        style="max-width: 600px"
        v-loading="loading"
      >
        <!-- Password Change Section -->
        <el-alert
          v-if="isDefaultPassword"
          title="安全提醒"
          type="warning"
          description="您正在使用默认密码，请尽快修改密码以确保安全。"
          show-icon
          :closable="false"
          style="margin-bottom: 20px"
        />

        <el-form-item label="当前密码">
          <el-input
            v-model="passwordForm.current_password"
            type="password"
            placeholder="请输入当前密码"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item label="新密码">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            placeholder="请输入新密码（至少6位）"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item label="确认新密码">
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="changePassword" :loading="savingPassword">
            修改密码
          </el-button>
          <span v-if="isDefaultPassword" style="margin-left: 10px; color: #E6A23C; font-size: 12px;">
            默认密码: admin123
          </span>
        </el-form-item>

        <el-divider />

        <!-- Bot Token -->
        <el-form-item label="Bot Token">
          <el-input
            v-model="form.bot_token"
            :type="showToken ? 'text' : 'password'"
            placeholder="请输入 Telegram Bot Token"
            clearable
          >
            <template #append>
              <el-button @click="showToken = !showToken">
                <el-icon>
                  <View v-if="!showToken" />
                  <Hide v-else />
                </el-icon>
              </el-button>
            </template>
          </el-input>
          <div class="form-tip">
            从 @BotFather 获取的 Bot Token，格式如：123456789:ABCdefGHI...
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveBotToken" :loading="savingToken">
            保存 Bot Token
          </el-button>
          <el-tag v-if="botRunning" type="success" style="margin-left: 10px">
            <el-icon style="vertical-align: middle; margin-right: 4px"><CircleCheck /></el-icon>
            Bot 运行中
          </el-tag>
          <el-tag v-else-if="tokenConfigured" type="warning" style="margin-left: 10px">
            <el-icon style="vertical-align: middle; margin-right: 4px"><Warning /></el-icon>
            Token 已配置但 Bot 未运行
          </el-tag>
          <el-tag v-else type="danger" style="margin-left: 10px">
            <el-icon style="vertical-align: middle; margin-right: 4px"><CircleClose /></el-icon>
            未配置
          </el-tag>
        </el-form-item>

        <el-divider />

        <!-- Admin IDs -->
        <el-form-item label="管理员 ID">
          <el-input
            v-model="form.admin_tg_ids"
            placeholder="多个 ID 用逗号分隔"
            clearable
          />
          <div class="form-tip">
            Telegram 用户 ID，可从 @userinfobot 获取。多个管理员用逗号分隔，如：123456,789012
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveAdminIds" :loading="savingAdmins">
            保存管理员 ID
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { View, Hide, CircleCheck, CircleClose, Warning } from '@element-plus/icons-vue'
import api, { setApiToken } from '../api'

const loading = ref(false)
const savingToken = ref(false)
const savingAdmins = ref(false)
const savingPassword = ref(false)
const showToken = ref(false)
const tokenConfigured = ref(false)
const botRunning = ref(false)
const isDefaultPassword = ref(false)

const form = ref({
  bot_token: '',
  admin_tg_ids: ''
})

const passwordForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: ''
})

const fetchSettings = async () => {
  loading.value = true
  try {
    // Check if bot token is configured
    const tokenCheck = await api.get('/settings/bot-token/exists')
    tokenConfigured.value = tokenCheck.configured

    // Get settings (includes bot_configured status)
    const res = await api.get('/settings')
    form.value.admin_tg_ids = res.admin_tg_ids || ''
    botRunning.value = res.bot_configured || false
    // Don't show masked token, keep empty for new input
    form.value.bot_token = ''

    // Check password status
    const pwdStatus = await api.get('/settings/password/status')
    isDefaultPassword.value = pwdStatus.is_default
  } catch (error) {
    ElMessage.error('获取设置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const changePassword = async () => {
  if (!passwordForm.value.current_password) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!passwordForm.value.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (passwordForm.value.new_password.length < 6) {
    ElMessage.warning('新密码至少需要6位')
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  savingPassword.value = true
  try {
    const res = await api.put('/settings/password', {
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password
    })

    if (res.status === 'ok') {
      ElMessage.success('密码修改成功！请使用新密码重新登录')
      // Update stored token
      setApiToken(passwordForm.value.new_password)
      // Clear form
      passwordForm.value = {
        current_password: '',
        new_password: '',
        confirm_password: ''
      }
      isDefaultPassword.value = false
    } else {
      ElMessage.error(res.message || '修改失败')
    }
  } catch (error) {
    ElMessage.error('修改失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    savingPassword.value = false
  }
}

const saveBotToken = async () => {
  if (!form.value.bot_token.trim()) {
    ElMessage.warning('请输入 Bot Token')
    return
  }

  savingToken.value = true
  try {
    const res = await api.put('/settings/bot-token', {
      bot_token: form.value.bot_token.trim()
    })

    // Note: axios interceptor already unwraps response.data, so res is the data directly
    if (res.status === 'ok') {
      ElMessage.success('Bot Token 已保存并成功热加载！')
      tokenConfigured.value = true
      botRunning.value = true
    } else if (res.status === 'warning') {
      ElMessage.warning(res.message)
      tokenConfigured.value = true
    } else {
      ElMessage.error(res.message || '保存失败')
    }

    form.value.bot_token = ''
    // Refresh status
    await fetchSettings()
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    savingToken.value = false
  }
}

const saveAdminIds = async () => {
  if (!form.value.admin_tg_ids.trim()) {
    ElMessage.warning('请输入管理员 ID')
    return
  }

  savingAdmins.value = true
  try {
    const res = await api.put('/settings/admin-ids', {
      admin_tg_ids: form.value.admin_tg_ids.trim()
    })
    ElMessage.success(res.message || '管理员 ID 已保存')
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    savingAdmins.value = false
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<style scoped>
.settings-page {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
