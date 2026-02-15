<script setup>
import { reactive, ref } from "vue";
import api from "@/api/axios.js";

const emit = defineEmits(['handleAuth'])

const isRegisterMode = ref(false);
const errorMessage = ref("");
const isLoading = ref(false);

const form = reactive({
  name: "",
  age: "",
  password: ""
});

const performLogin = async () => {
  const formData = new FormData();
  formData.append("username", form.name);
  formData.append("password", form.password);

  const response = await api.post("/auth/token", formData);

  const token = response.data.access_token;

  localStorage.setItem('user_token', token);
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  emit("handleAuth");
};

const handleSubmit = async () => {
  errorMessage.value = "";
  isLoading.value = true;

  try {
    if (isRegisterMode.value) {
      await api.post("/users/", {
        name: form.name,
        age: form.age,
        password: form.password,
      });
    }

    await performLogin();

  } catch (error) {
    console.error(error);
    if (error.response && error.response.status === 401) {
      errorMessage.value = "Невірне ім'я або пароль";
    } else if (isRegisterMode.value) {
      errorMessage.value = "Помилка реєстрації. Можливо, ім'я зайняте.";
    } else {
      errorMessage.value = "Сталася помилка сервера.";
    }
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <div class="tabs">
        <button
            :class="{ active: !isRegisterMode }"
            @click="isRegisterMode = false">
          Вхід
        </button>
        <button
            :class="{ active: isRegisterMode }"
            @click="isRegisterMode = true">
          Реєстрація
        </button>
      </div>

      <h2>{{ isRegisterMode ? 'Створити акаунт' : 'З поверненням!' }}</h2>

      <form @submit.prevent="handleSubmit">

        <div class="input-group">
          <label>Ім'я</label>
          <input
              type="text"
              v-model="form.name"
              placeholder="Введіть ваше ім'я"
              required
          />
        </div>

        <div class="input-group" v-if="isRegisterMode">
          <label>Вік</label>
          <input
              type="number"
              v-model="form.age"
              placeholder="Скільки вам років?"
              required
          />
        </div>

        <div class="input-group">
          <label>Пароль</label>
          <input
              type="password"
              v-model="form.password"
              placeholder="••••••••"
              required
          />
        </div>

        <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>

        <button type="submit" class="submit-btn" :disabled="isLoading">
          {{ isLoading ? 'Завантаження...' : (isRegisterMode ? 'Зареєструватися' : 'Увійти') }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 50vh;
}

.auth-card {
  background: #1e1e1e;
  padding: 2rem;
  border-radius: 16px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  border: 1px solid #333;
}

h2 {
  color: #fff;
  text-align: center;
  margin-bottom: 1.5rem;
  font-weight: 600;
}

.tabs {
  display: flex;
  background: #2c2c2c;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 2rem;
}

.tabs button {
  flex: 1;
  background: transparent;
  border: none;
  color: #888;
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
}

.tabs button.active {
  background: #42b883;
  color: #fff;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}


.input-group {
  margin-bottom: 1.2rem;
}

.input-group label {
  display: block;
  color: #aaa;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.input-group input {
  width: 100%;
  padding: 12px;
  background: #2c2c2c;
  border: 1px solid #444;
  border-radius: 8px;
  color: #fff;
  font-size: 1rem;
  transition: border-color 0.3s;
  box-sizing: border-box;
}

.input-group input:focus {
  outline: none;
  border-color: #42b883;
}

.submit-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #42b883 0%, #35495e 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: transform 0.2s, opacity 0.2s;
  margin-top: 1rem;
}

.submit-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.submit-btn:disabled {
  background: #555;
  cursor: not-allowed;
  transform: none;
}

.error-msg {
  color: #ff6b6b;
  font-size: 0.9rem;
  text-align: center;
  margin-top: 10px;
}
</style>