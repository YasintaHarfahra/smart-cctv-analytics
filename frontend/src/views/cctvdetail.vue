<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import axios from "axios";
import Hls from "hls.js";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

const cctv = ref(null);
const isLoading = ref(false);
const error = ref(null);
let hls = null;

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json", Accept: "application/json" },
});

const fetchCctvDetail = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    const res = await http.get(`/cctv/${route.params.id}`);
    cctv.value = res.data;

    const video = document.getElementById("cctv-player");
    if (!video) return;

    // 🔥 Pakai proxy supaya tidak kena CORS/download
    const proxiedUrl = `/api/proxy?url=${encodeURIComponent(cctv.value.link)}`;

    if (Hls.isSupported()) {
      hls = new Hls({
        debug: false,
        xhrSetup: function (xhr, url) {
          // Semua request segmen diarahkan ke proxy juga
          xhr.open("GET", `/api/proxy?url=${encodeURIComponent(url)}`, true);
        },
      });
      hls.loadSource(proxiedUrl);
      hls.attachMedia(video);
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari punya native support
      video.src = proxiedUrl;
    }
  } catch (err) {
    console.error(err);
    error.value = "Gagal load detail CCTV";
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchCctvDetail);

onBeforeUnmount(() => {
  if (hls) {
    hls.destroy();
  }
});
</script>

<template>
  <div class="container mx-auto p-6">
    <button
      @click="router.back()"
      class="mb-4 px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
    >
      ← Back
    </button>

    <div v-if="isLoading">Loading...</div>
    <div v-else-if="error" class="text-red-500">{{ error }}</div>
    <div v-else-if="cctv">
      <h1 class="text-2xl font-bold mb-4">
        {{ cctv.location }} ({{ cctv.type }})
      </h1>
      <video
        id="cctv-player"
        controls
        autoplay
        class="w-full max-w-3xl rounded-lg shadow-lg"
      ></video>
    </div>
  </div>
</template>
