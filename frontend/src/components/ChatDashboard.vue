<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import api from '@/api/axios.js' // Твій налаштований axios

// --- СТАН ДАНИХ ---
const currentUser = ref(null)
const users = ref([])
const selectedUser = ref(null)
const messages = ref([])
const messageInput = ref("")
const socket = ref(null)
const messagesContainer = ref(null) // Для автоскролу

// Отримуємо поточного юзера та список всіх інших
onMounted(async () => {
  try {
    // 1. Хто я?
    const meRes = await api.get('/users/me')
    currentUser.value = meRes.data

    // 2. Хто ще є? (потрібен ендпоінт /users/all)
    const allRes = await api.get('/users/all')

    // Фільтруємо, щоб не показувати себе в списку контактів
    users.value = allRes.data.filter(u => u.id !== currentUser.value.id)
  } catch (e) {
    console.error("Помилка завантаження даних", e)
  }
})

// При виході закриваємо сокет
onUnmounted(() => {
  if (socket.value) socket.value.close()
})

// --- ЛОГІКА ЧАТУ ---

// Функція вибору співрозмовника
const selectUser = (user) => {
  if (selectedUser.value?.id === user.id) return // Вже обраний

  selectedUser.value = user
  messages.value = [] // Очищаємо чат при перемиканні
  connectWebSocket()
}

// Генерація унікального ID кімнати для двох людей
const getRoomId = (userId1, userId2) => {
  // Сортуємо ID, щоб 1+5 і 5+1 давали одну кімнату
  const min = Math.min(userId1, userId2)
  const max = Math.max(userId1, userId2)
  return min * 100000 + max
}

const connectWebSocket = () => {
  if (socket.value) {
    socket.value.close()
  }

  const roomId = getRoomId(currentUser.value.id, selectedUser.value.id)

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const wsBaseUrl = apiUrl.replace('http', 'ws');

  const wsUrl = `${wsBaseUrl}/ws/chat/${roomId}/${currentUser.value.id}?username=${currentUser.value.name}`

  console.log("Connecting to WebSocket:", wsUrl);


  socket.value = new WebSocket(wsUrl)

  socket.value.onopen = () => {
    console.log("Chat connected")
  }

  socket.value.onmessage = (event) => {
    const data = JSON.parse(event.data)
    // data приходить у форматі: { message: "...", is_self: true/false }
    messages.value.push(data)
    scrollToBottom()
  }

  socket.value.onclose = () => {
    console.log("Chat disconnected")
  }
}

const sendMessage = () => {
  if (!messageInput.value.trim() || !socket.value) return

  // Відправляємо JSON об'єкт (сервер очікує receive_json)
  const payload = {
    text: messageInput.value // Можна розширити (додати час, тип тощо)
  }

  socket.value.send(JSON.stringify(payload))
  messageInput.value = ""
}

// Автоскрол до низу
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// Еміт для logout (щоб передати в App.vue)
const emit = defineEmits(['logout'])
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
            <span class="user-status">Online</span>
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
            <span class="header-details">ID: {{ selectedUser.id }}</span>
          </div>
        </header>

        <div class="messages-list" ref="messagesContainer">
          <div
              v-for="(msg, index) in messages"
              :key="index"
              class="message-row"
              :class="{ 'my-message-row': msg.is_self }"
          >
            <div class="bubble">
              {{ typeof msg.message === 'object' && msg.message.text ? msg.message.text : msg.message }}
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
/* Layout */
.chat-container {
  display: flex;
  height: 85vh; /* Висота чату */
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}

/* Sidebar Styling */
.sidebar {
  width: 300px;
  background: #252525;
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #333;
}

.sidebar-header h3 { margin: 0 0 10px 0; color: #fff;}

.my-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.9rem;
  color: #888;
}

.users-list {
  flex: 1;
  overflow-y: auto;
}

.user-item {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #2a2a2a;
}

.user-item:hover { background: #2f2f2f; }
.user-item.active { background: #333; border-left: 4px solid #42b883; }

.avatar, .avatar-small {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #42b883, #35495e);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
  margin-right: 15px;
  flex-shrink: 0;
}
.avatar-small { width: 24px; height: 24px; font-size: 0.8rem; margin-right: 5px; }

.user-info { display: flex; flex-direction: column; }
.user-name { color: #fff; font-weight: 500; }
.user-status { color: #666; font-size: 0.8rem; }
.no-users { padding: 20px; color: #666; text-align: center; }

.sidebar-footer { padding: 15px; border-top: 1px solid #333; }
.logout-btn-small {
  width: 100%;
  background: #ff4757;
  border: none;
  color: white;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}

/* Main Chat Area */
.chat-area {
  flex: 1;
  background: #121212;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* Empty State */
.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #444;
}
.placeholder-icon { font-size: 4rem; margin-bottom: 20px; opacity: 0.5; }

/* Active Chat Window */
.chat-window { display: flex; flex-direction: column; height: 100%; }

.chat-header {
  padding: 15px 20px;
  background: #1e1e1e;
  border-bottom: 1px solid #333;
  display: flex;
  align-items: center;
}
.header-info { display: flex; flex-direction: column; }
.header-name { color: #fff; font-weight: bold; }
.header-details { color: #666; font-size: 0.8rem; }

/* Messages List */
.messages-list {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message-row { display: flex; justify-content: flex-start; }
.my-message-row { justify-content: flex-end; }

.bubble {
  max-width: 70%;
  padding: 10px 15px;
  border-radius: 12px;
  font-size: 0.95rem;
  line-height: 1.4;
  word-wrap: break-word;
}

.message-row .bubble {
  background: #252525;
  color: #ddd;
  border-top-left-radius: 0;
}

.my-message-row .bubble {
  background: #42b883;
  color: #000;
  border-top-right-radius: 0;
  border-top-left-radius: 12px;
}

/* Input Area */
.input-area {
  padding: 20px;
  background: #1e1e1e;
  border-top: 1px solid #333;
  display: flex;
  gap: 10px;
}

.input-area input {
  flex: 1;
  background: #2c2c2c;
  border: 1px solid #444;
  padding: 12px;
  border-radius: 20px;
  color: white;
  outline: none;
}
.input-area input:focus { border-color: #42b883; }

.send-btn {
  background: #42b883;
  border: none;
  width: 45px;
  height: 45px;
  border-radius: 50%;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  transition: transform 0.2s;
}
.send-btn:hover { transform: scale(1.1); }
</style>