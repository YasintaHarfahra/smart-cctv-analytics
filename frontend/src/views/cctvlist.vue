<script setup>
import { ref, onMounted } from "vue";
import axios from "axios";
import { useRouter } from "vue-router";

const cctvs = ref([]);
const isLoading = ref(false);
const error = ref(null);
const router = useRouter();

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json", Accept: "application/json" },
});

const fetchCctvs = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    const res = await http.get("/cctv");
    cctvs.value = res.data.devices || [];   
  } catch (err) {
    console.error(err);
    error.value = "Failed to load CCTV list";
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchCctvs);

const goToDetail = (id) => {
  router.push({ name: "cctvdetail", params: { id } });
};
</script>

<template>
  <div class="container mx-auto p-6">
    <h1 class="text-3xl font-bold mb-6">📹 Daftar CCTV</h1>

    <div v-if="isLoading">Loading...</div>
    <div v-else-if="error" class="text-red-500">{{ error }}</div>

    <ul v-else class="space-y-2">
      <li
        v-for="cctv in cctvs"
        :key="cctv.id"
        @click="goToDetail(cctv.id)"
        class="cursor-pointer p-3 rounded-lg hover:bg-gray-100 border"
      >
        {{ cctv.location }} ({{ cctv.type }})
      </li>
    </ul>
  </div>
</template>
