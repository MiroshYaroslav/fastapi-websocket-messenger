<script setup>
import { ref, onMounted } from 'vue'
import api from "@/api/axios.js";
import AuthComponent from './components/AuthComponent.vue'
import ChatDashboard from './components/ChatDashboard.vue' // <--- Імпорт

const isAuth = ref(false)

const handleAuth = () => {
  isAuth.value = true
}

const logout = () => {
  localStorage.removeItem('user_token')
  delete api.defaults.headers.common['Authorization']
  isAuth.value = false
}

onMounted(() => {
  const token = localStorage.getItem('user_token')
  if (token) {
    isAuth.value = true
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
  }
})
</script>

<template>
  <div id="app-container">
    <header>
      <div class="logo">My App</div>
    </header>

    <main>
      <AuthComponent v-if="!isAuth" @handleAuth="handleAuth" />

      <ChatDashboard v-else @logout="logout" />
    </main>
  </div>
</template>

<style>
/* ... (твій старий стиль body і header) ... */

body {
  margin: 0;
  padding: 0;
  background-color: #121212;
  color: #ffffff;
  font-family: 'Inter', sans-serif;
}

#app-container {
  max-width: 1400px; /* Трохи розширимо контейнер для чату */
  margin: 0 auto;
  padding: 20px;
}

header {
  padding: 20px 0;
  border-bottom: 1px solid #333;
  margin-bottom: 20px;
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
  color: #42b883;
}
</style>