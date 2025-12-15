import axios from 'axios'
import { ElMessage } from 'element-plus'

// Get API token from localStorage or use default
const getApiToken = () => localStorage.getItem('apiToken') || ''

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = getApiToken()
    if (token) {
      config.headers['X-API-Token'] = token
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// Set API token
export const setApiToken = (token) => {
  localStorage.setItem('apiToken', token)
}

// Health check
export const getHealth = () => api.get('/health')

// Channels
export const getChannels = () => api.get('/channels')
export const getChannel = (id) => api.get(`/channels/${id}`)
export const deleteChannel = (id) => api.delete(`/channels/${id}`)

// Groups
export const getGroups = () => api.get('/groups')
export const getGroup = (id) => api.get(`/groups/${id}`)
export const createGroup = (data) => api.post('/groups', data)
export const updateGroup = (id, data) => api.put(`/groups/${id}`, data)
export const deleteGroup = (id) => api.delete(`/groups/${id}`)
export const getGroupChannels = (id) => api.get(`/groups/${id}/channels`)
export const addChannelsToGroup = (id, channelIds) => api.post(`/groups/${id}/channels`, { channel_ids: channelIds })
export const removeChannelFromGroup = (groupId, channelId) => api.delete(`/groups/${groupId}/channels/${channelId}`)

// Slots
export const getSlots = (groupId = null) => {
  const params = groupId ? { group_id: groupId } : {}
  return api.get('/slots', { params })
}
export const getSlot = (id) => api.get(`/slots/${id}`)
export const createSlot = (data) => api.post('/slots', data)
export const updateSlot = (id, data) => api.put(`/slots/${id}`, data)
export const deleteSlot = (id) => api.delete(`/slots/${id}`)
export const enableSlot = (id) => api.post(`/slots/${id}/enable`)
export const disableSlot = (id) => api.post(`/slots/${id}/disable`)

// Creatives
export const getCreatives = (slotId = null) => {
  const params = slotId ? { slot_id: slotId } : {}
  return api.get('/creatives', { params })
}
export const getUnboundCreatives = () => api.get('/creatives/unbound')
export const getCreative = (id) => api.get(`/creatives/${id}`)
export const updateCreative = (id, data) => api.put(`/creatives/${id}`, data)
export const deleteCreative = (id) => api.delete(`/creatives/${id}`)
export const bindCreative = (creativeId, slotId) => api.post(`/creatives/${creativeId}/bind/${slotId}`)
export const unbindCreative = (id) => api.post(`/creatives/${id}/unbind`)

export default api
