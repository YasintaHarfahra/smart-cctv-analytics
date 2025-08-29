import { createApp } from 'vue'
import App from './App.vue'
import router from './router' // WAJIB: Impor router yang sudah Anda buat
import './assets/main.css'

const app = createApp(App)

app.use(router) // WAJIB: Instruksikan Vue untuk menggunakan router

app.mount('#app')