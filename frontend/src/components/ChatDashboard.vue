<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import api from '@/api/axios.js'

const currentUser = ref(null)
const users = ref([])
const selectedUser = ref(null)
const messages = ref([])
const isLoadingHistory = ref(false)
const hasMoreHistory = ref(true)
const messageInput = ref("")
const socket = ref(null)
const globalSocket = ref(null)
const messagesContainer = ref(null)
const unreadCounts = ref({})

const onlineUsers = ref({})

const emit = defineEmits(['logout'])

let reconnectGlobalTimeout = null;
let reconnectChatTimeout = null;

onMounted(async () => {
  try {
    const meRes = await api.get('/users/me')
    currentUser.value = meRes.data

    const allRes = await api.get('/users/all')
    users.value = allRes.data.filter(u => u.id !== currentUser.value.id)

    try {
      const unreadRes = await api.get('/ws/unread')
      users.value.forEach(u => {
        unreadCounts.value[u.id] = unreadRes.data[u.id] || 0
      })
    } catch (unreadErr) {
      console.warn("Не вдалося завантажити лічильники", unreadErr)
      users.value.forEach(u => { unreadCounts.value[u.id] = 0 })
    }

    try {
      const onlineRes = await api.get('/ws/online-users')
      const onlineIds = onlineRes.data.online_users || []
      onlineIds.forEach(id => {
        onlineUsers.value[id] = true
      })
    } catch (e) {
      console.warn("Не вдалося завантажити початковий онлайн-статус", e)
    }

    connectGlobalWebSocket()
  } catch (e) {
    console.error(e)
    if (e.response && e.response.status === 401) {
      emit('logout')
    }
  }
})

onUnmounted(() => {
  clearTimeout(reconnectGlobalTimeout)
  clearTimeout(reconnectChatTimeout)

  if (socket.value) {
    socket.value.onclose = null
    socket.value.close()
  }
  if (globalSocket.value) {
    globalSocket.value.onclose = null
    globalSocket.value.close()
  }
})

const selectUser = async (user) => {
  if (selectedUser.value?.id === user.id) return

  selectedUser.value = user
  messages.value = []

  unreadCounts.value[user.id] = 0

  try {
    await api.post(`/ws/mark-read/${user.id}`)
  } catch (e) {
    console.error("Помилка при оновленні статусу прочитання", e)
  }

  hasMoreHistory.value = true
  connectWebSocket()
}

const getRoomId = (userId1, userId2) => {
  const min = Math.min(userId1, userId2)
  const max = Math.max(userId1, userId2)
  return min * 100000 + max
}

const getWsBaseUrl = () => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  return apiUrl.replace('http', 'ws')
}

const connectGlobalWebSocket = () => {
  const wsUrl = `${getWsBaseUrl()}/ws/notifications/${currentUser.value.id}`
  globalSocket.value = new WebSocket(wsUrl)

  globalSocket.value.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'new_message') {
      if (selectedUser.value?.id !== data.from_user_id) {
        unreadCounts.value[data.from_user_id] = (unreadCounts.value[data.from_user_id] || 0) + 1
      }
    }
    else if (data.type === 'presence_update') {
      onlineUsers.value[data.user_id] = data.is_online
    }
  }

  globalSocket.value.onclose = (e) => {
    console.warn("Глобальний сокет закрито. Спроба відновлення через 3 сек...")
    clearTimeout(reconnectGlobalTimeout)
    reconnectGlobalTimeout = setTimeout(() => {
      if (currentUser.value) {
        connectGlobalWebSocket()
      }
    }, 3000)
  }
}

const connectWebSocket = () => {
  if (socket.value) {
    socket.value.onclose = null
    socket.value.close()
  }

  const roomId = getRoomId(currentUser.value.id, selectedUser.value.id)
  const wsUrl = `${getWsBaseUrl()}/ws/chat/${roomId}/${currentUser.value.id}/${selectedUser.value.id}?username=${currentUser.value.name}`

  socket.value = new WebSocket(wsUrl)

  socket.value.onmessage = (event) => {
    const data = JSON.parse(event.data)
    messages.value.push(data)
    scrollToBottom()
  }

  socket.value.onclose = (e) => {
    console.warn("Сокет чату закрито. Спроба відновлення через 3 сек...")
    clearTimeout(reconnectChatTimeout)
    reconnectChatTimeout = setTimeout(() => {
      if (selectedUser.value) {
        connectWebSocket()
      }
    }, 3000)
  }
}

const handleScroll = async () => {
  if (!messagesContainer.value) return;

  if (messagesContainer.value.scrollTop === 0 && !isLoadingHistory.value && hasMoreHistory.value) {
    await loadOlderMessages();
  }
};

const loadOlderMessages = async () => {
  isLoadingHistory.value = true;
  const roomId = getRoomId(currentUser.value.id, selectedUser.value.id);
  const currentOffset = messages.value.length;

  try {
    const oldScrollHeight = messagesContainer.value.scrollHeight;

    const res = await api.get(`/ws/history/${roomId}?offset=${currentOffset}`);
    const olderMessages = res.data;

    if (olderMessages.length < 10) {
      hasMoreHistory.value = false;
    }

    messages.value = [...olderMessages, ...messages.value];

    nextTick(() => {
      const newScrollHeight = messagesContainer.value.scrollHeight;
      messagesContainer.value.scrollTop = newScrollHeight - oldScrollHeight;
    });

  } catch (e) {
    console.error("Помилка завантаження історії", e);
  } finally {
    isLoadingHistory.value = false;
  }
};

const sendMessage = () => {
  if (!messageInput.value.trim() || !socket.value) return

  const payload = { text: messageInput.value }
  socket.value.send(JSON.stringify(payload))
  messageInput.value = ""
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}
</script>

<template>
  <div class="chat-container">

    <aside class="sidebar">
      <div class="sidebar-header">
        <h3>Чати</h3>
        <div class="my-profile" v-if="currentUser">
          <div class="avatar-small">{{ currentUser.name[0] }}</div>
          <span>{{ currentUser.name }} (Ви)</span>
        </div>
      </div>

      <div class="users-list">
        <div
            v-for="user in users"
            :key="user.id"
            class="user-item"
            :class="{ active: selectedUser?.id === user.id }"
            @click="selectUser(user)"
        >
          <div class="avatar">{{ user.name[0].toUpperCase() }}</div>
          <div class="user-info">
            <span class="user-name">{{ user.name }}</span>
            <span class="user-status" :class="{ 'text-online': onlineUsers[user.id] }">
              <span class="status-dot" :class="{ 'online': onlineUsers[user.id] }"></span>
              {{ onlineUsers[user.id] ? 'Онлайн' : 'Офлайн' }}
            </span>
          </div>
          <div class="unread-badge" v-if="unreadCounts[user.id] > 0">
            {{ unreadCounts[user.id] }}
          </div>
        </div>

        <div v-if="users.length === 0" class="no-users">
          Немає інших користувачів :(
        </div>
      </div>

      <div class="sidebar-footer">
        <button @click="$emit('logout')" class="logout-btn-small">Вихід</button>
      </div>
    </aside>

    <main class="chat-area">

      <div v-if="!selectedUser" class="empty-state">
        <div class="placeholder-icon">💬</div>
        <h3>Оберіть, кому написати</h3>
      </div>

      <div v-else class="chat-window">
        <header class="chat-header">
          <div class="avatar">{{ selectedUser.name[0].toUpperCase() }}</div>
          <div class="header-info">
            <span class="header-name">{{ selectedUser.name }}</span>
            <span class="header-details" :class="{ 'text-online': onlineUsers[selectedUser.id] }">
              {{ onlineUsers[selectedUser.id] ? 'Онлайн' : 'Офлайн' }}
            </span>
          </div>
        </header>

        <div class="messages-list" ref="messagesContainer" @scroll="handleScroll">
          <div
              v-for="(msg, index) in messages"
              :key="index"
              class="message-row"
              :class="{ 'my-message-row': msg.is_self }"
          >
            <div class="bubble">
              {{ msg.text }}
            </div>
          </div>
        </div>

        <div class="input-area">
          <input
              v-model="messageInput"
              @keyup.enter="sendMessage"
              type="text"
              placeholder="Написати повідомлення..."
          />
          <button @click="sendMessage" class="send-btn">
            ➤
          </button>
        </div>
      </div>

    </main>
  </div>
</template>

<style scoped>
.chat-container { display: flex; height: 85vh; background: #1e1e1e; border: 1px solid #333; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
.sidebar { width: 300px; background: #252525; border-right: 1px solid #333; display: flex; flex-direction: column; }
.sidebar-header { padding: 20px; border-bottom: 1px solid #333; }
.sidebar-header h3 { margin: 0 0 10px 0; color: #fff;}
.my-profile { display: flex; align-items: center; gap: 10px; font-size: 0.9rem; color: #888; }
.users-list { flex: 1; overflow-y: auto; }
.user-item { display: flex; align-items: center; padding: 15px 20px; cursor: pointer; transition: background 0.2s; border-bottom: 1px solid #2a2a2a; }
.user-item:hover { background: #2f2f2f; }
.user-item.active { background: #333; border-left: 4px solid #42b883; }
.avatar, .avatar-small { width: 40px; height: 40px; background: linear-gradient(135deg, #42b883, #35495e); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; margin-right: 15px; flex-shrink: 0; }
.avatar-small { width: 24px; height: 24px; font-size: 0.8rem; margin-right: 5px; }
.user-info { display: flex; flex-direction: column; }
.user-name { color: #fff; font-weight: 500; }

.user-status {
  color: #666;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  transition: color 0.3s;
}
.status-dot {
  width: 8px;
  height: 8px;
  background: #666;
  border-radius: 50%;
  transition: all 0.3s;
}
.status-dot.online {
  background: #42b883;
  box-shadow: 0 0 6px rgba(66, 184, 131, 0.6);
}
.text-online { color: #42b883; }

.unread-badge { background: #42b883; color: #000; font-size: 0.8rem; font-weight: bold; padding: 2px 8px; border-radius: 12px; margin-left: auto; }
.no-users { padding: 20px; color: #666; text-align: center; }
.sidebar-footer { padding: 15px; border-top: 1px solid #333; }
.logout-btn-small { width: 100%; background: #ff4757; border: none; color: white; padding: 8px; border-radius: 6px; cursor: pointer; }
.chat-area { flex: 1; background: #121212; position: relative; display: flex; flex-direction: column; }
.empty-state { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #444; }
.placeholder-icon { font-size: 4rem; margin-bottom: 20px; opacity: 0.5; }
.chat-window { display: flex; flex-direction: column; height: 100%; }
.chat-header { padding: 15px 20px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; }
.header-info { display: flex; flex-direction: column; }
.header-name { color: #fff; font-weight: bold; }
.header-details { color: #666; font-size: 0.8rem; transition: color 0.3s; }
.messages-list { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.message-row { display: flex; justify-content: flex-start; }
.my-message-row { justify-content: flex-end; }
.bubble { max-width: 70%; padding: 10px 15px; border-radius: 12px; font-size: 0.95rem; line-height: 1.4; word-wrap: break-word; }
.message-row .bubble { background: #252525; color: #ddd; border-top-left-radius: 0; }
.my-message-row .bubble { background: #42b883; color: #000; border-top-right-radius: 0; border-top-left-radius: 12px; }
.input-area { padding: 20px; background: #1e1e1e; border-top: 1px solid #333; display: flex; gap: 10px; }
.input-area input { flex: 1; background: #2c2c2c; border: 1px solid #444; padding: 12px; border-radius: 20px; color: white; outline: none; }
.input-area input:focus { border-color: #42b883; }
.send-btn { background: #42b883; border: none; width: 45px; height: 45px; border-radius: 50%; color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; transition: transform 0.2s; }
.send-btn:hover { transform: scale(1.1); }
</style>