<script setup>
import { ref, onMounted, onUnmounted, computed } from "vue";
import axios from "axios";
import { Bar } from "vue-chartjs";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// State Management
const analyticsData = ref([]);
const totalCounts = ref({});
const isLoading = ref(false);
const error = ref(null);
let intervalId = null;

// Environment Variables & Configuration
const API_URL = import.meta.env.VITE_BACKEND_API_URL || "http://localhost:8000";
const VIDEO_STREAM_URL = import.meta.env.VITE_VIDEO_STREAM_URL || "http://localhost:8000/video_feed";

// In your frontend API configuration
const http = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  withCredentials: true
});

// Enhanced fetchData function with better error handling
const fetchData = async () => {
  isLoading.value = true;
  error.value = null;

  try {
    const response = await http.get("/analytics/", { 
      params: { limit: 50 },
      // Add retry logic
      retry: 3,
      retryDelay: (retryCount) => retryCount * 1000
    });
    
    console.log("API Response:", response); // For debugging

    if (!response.data) {
      throw new Error("No data received");
    }

    analyticsData.value = Array.isArray(response.data) ? response.data : [];
    
    const counts = {};
    for (const item of analyticsData.value) {
      counts[item.object_type] = (counts[item.object_type] || 0) + item.count;
    }
    totalCounts.value = counts;

  } catch (err) {
    console.error("Detailed error:", {
      message: err.message,
      response: err.response,
      status: err.response?.status
    });
    error.value = "Connection error. Please check if the backend server is running.";
  } finally {
    isLoading.value = false;
  }
};

// Lifecycle Hooks
onMounted(() => {
  fetchData();
  intervalId = setInterval(fetchData, 5000);
});

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
});

// Chart Configuration
const chartData = computed(() => ({
  labels: Object.keys(totalCounts.value),
  datasets: [
    {
      label: "Total Objects Detected",
      data: Object.values(totalCounts.value),
      backgroundColor: [
        "rgba(255, 99, 132, 0.6)",
        "rgba(54, 162, 235, 0.6)",
        "rgba(255, 206, 86, 0.6)",
        "rgba(75, 192, 192, 0.6)",
        "rgba(153, 102, 255, 0.6)",
        "rgba(255, 159, 64, 0.6)",
      ],
      borderWidth: 1,
    },
  ],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: "top" },
    title: { display: true, text: "Live Object Detection Counts by Type" },
  },
};

// Enhanced video error handler
const handleVideoError = (e) => {
  console.error("Video stream error:", e);
  error.value = "Video stream unavailable. Retrying...";
  
  // Retry loading video after delay
  setTimeout(() => {
    const videoElement = document.querySelector('img[alt="Live CCTV"]');
    if (videoElement) {
      videoElement.src = `${VIDEO_STREAM_URL}?t=${Date.now()}`;
    }
  }, 3000);
};
</script>

<template>
  <div class="min-h-screen flex flex-col bg-gray-50">
    <!-- Navbar -->
    <nav class="bg-green-700 text-white shadow-md sticky top-0 z-50">
      <div class="container mx-auto flex justify-between items-center px-6 py-4">
        <h1 class="text-2xl font-bold">🌐 Smart CCTV</h1>
        <ul class="hidden md:flex space-x-6 text-sm">
          <li><a href="#" class="hover:text-gray-200">Dashboard</a></li>
          <li><a href="#" class="hover:text-gray-200">Analytics</a></li>
          <li><a href="#" class="hover:text-gray-200">Settings</a></li>
        </ul>
      </div>
    </nav>

    <!-- Hero Header -->
    <header class="bg-white shadow-sm">
      <div class="container mx-auto px-6 py-10 text-center">
        <h2 class="text-3xl md:text-4xl font-bold text-gray-800 mb-2">
          Smart CCTV Analytics Dashboard
        </h2>
        <p class="text-gray-600">
          Real-time monitoring & object detection visualization
        </p>
      </div>
    </header>

    <!-- Main -->
    <main class="flex-1 container mx-auto px-6 py-8 grid gap-8 md:grid-cols-2">
      <!-- CCTV Feed -->
      <section class="bg-white rounded-2xl shadow-md p-6 flex flex-col">
        <h3 class="text-lg font-semibold mb-4 border-b pb-2">📹 Live CCTV Feed</h3>
        <div class="relative">
          <img
            :src="VIDEO_STREAM_URL"
            alt="Live CCTV"
            class="rounded-lg border shadow-md max-h-[400px] object-cover mx-auto"
            @error="handleVideoError"
          />
          <div v-if="error" class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 rounded-lg">
            <p class="text-white text-center p-4">{{ error }}</p>
          </div>
        </div>
      </section>

      <!-- Chart -->
      <section class="bg-white rounded-2xl shadow-md p-6 flex flex-col">
        <h3 class="text-lg font-semibold mb-4 border-b pb-2">📊 Object Distribution</h3>
        <div v-if="isLoading" class="flex-1 flex items-center justify-center">
          <div class="animate-spin rounded-full h-12 w-12 border-4 border-green-500 border-t-transparent"></div>
        </div>
        <div v-else-if="error" class="flex-1 flex items-center justify-center">
          <p class="text-red-500">{{ error }}</p>
        </div>
        <div v-else-if="Object.keys(totalCounts).length > 0" class="h-[350px]">
          <Bar :data="chartData" :options="chartOptions" />
        </div>
        <p v-else class="text-gray-500 italic text-center">
          No detection data available yet...
        </p>
      </section>

      <!-- Logs -->
      <section class="md:col-span-2 bg-white rounded-2xl shadow-md p-6">
        <h3 class="text-lg font-semibold mb-4 border-b pb-2">📝 Recent Detections Log</h3>
        <div class="overflow-x-auto max-h-[400px] border rounded-lg">
          <table class="min-w-full text-sm text-left">
            <thead class="bg-green-700 text-white">
              <tr>
                <th class="px-4 py-2">Timestamp</th>
                <th class="px-4 py-2">Object Type</th>
                <th class="px-4 py-2">Count</th>
                <th class="px-4 py-2">Area</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(data, index) in analyticsData"
                :key="index"
                class="odd:bg-gray-50 even:bg-white hover:bg-green-50 transition"
              >
                <td class="px-4 py-2">{{ new Date(data.timestamp).toLocaleString() }}</td>
                <td class="px-4 py-2">{{ data.object_type }}</td>
                <td class="px-4 py-2">{{ data.count }}</td>
                <td class="px-4 py-2">{{ data.area }}</td>
              </tr>
              <tr v-if="analyticsData.length === 0">
                <td colspan="4" class="px-4 py-8 text-center text-gray-500 italic">
                  No detection data available...
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="bg-green-700 text-white text-center py-4">
      <p class="text-sm">
        &copy; {{ new Date().getFullYear() }} Smart CCTV Analytics — All Rights Reserved
      </p>
    </footer>
  </div>
</template>