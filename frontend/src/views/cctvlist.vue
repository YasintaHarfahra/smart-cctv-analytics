<script setup>
import { ref, onMounted, computed } from "vue";
import axios from "axios";
import { useRouter } from "vue-router";

const cctvs = ref([]);
const isLoading = ref(false);
const error = ref(null);
const router = useRouter();
const searchQuery = ref("");
const selectedCategory = ref("all");

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

// Computed properties for filtering
const filteredCctvs = computed(() => {
  let filtered = cctvs.value;
  
  // Filter by search query
  if (searchQuery.value) {
    filtered = filtered.filter(cctv => 
      cctv.location.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      cctv.type.toLowerCase().includes(searchQuery.value.toLowerCase())
    );
  }
  
  // Filter by category
  if (selectedCategory.value !== "all") {
    filtered = filtered.filter(cctv => cctv.category === selectedCategory.value);
  }
  
  return filtered;
});

const uniqueCategories = computed(() => {
  const categories = [...new Set(cctvs.value.map(cctv => cctv.category))];
  return categories.filter(cat => cat); // Remove empty categories
});

const getCategoryColor = (category) => {
  switch (category) {
    case "Dalam Kota":
      return "bg-green-100 text-green-800 border-green-200";
    case "Perbatasan Kota":
      return "bg-orange-100 text-orange-800 border-orange-200";
    case "Perbatasan Provinsi":
      return "bg-red-100 text-red-800 border-red-200";
    default:
      return "bg-gray-100 text-gray-800 border-gray-200";
  }
};

const getCameraNumber = (type) => {
  const match = type.match(/Camera\s*(\d+)/i);
  return match ? match[1] : type;
};

const formatCoordinates = (coords) => {
  if (!coords) return null;
  // Clean up coordinate string and format it
  const cleanCoords = coords.replace(/[^\d.,-]/g, '');
  return cleanCoords;
};
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header Section -->
    <div class="bg-white shadow-sm border-b">
      <div class="container mx-auto px-4 py-6">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 class="text-3xl font-bold text-gray-900">📹 Daftar CCTV</h1>
            <p class="text-gray-600 mt-1">Monitor dan kelola semua kamera CCTV yang tersedia</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm text-gray-500">Total: {{ cctvs.length }} kamera</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Filters Section -->
    <div class="bg-white border-b">
      <div class="container mx-auto px-4 py-4">
        <div class="flex flex-col sm:flex-row gap-4">
          <!-- Search Input -->
          <div class="flex-1">
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                v-model="searchQuery"
                type="text"
                placeholder="Cari lokasi atau tipe kamera..."
                class="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
          
          <!-- Category Filter -->
          <div class="sm:w-48">
            <select
              v-model="selectedCategory"
              class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">Semua Kategori</option>
              <option v-for="category in uniqueCategories" :key="category" :value="category">
                {{ category }}
              </option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="container mx-auto px-4 py-6">
      <!-- Loading State -->
      <div v-if="isLoading" class="flex justify-center items-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="text-center py-12">
        <div class="text-red-500 text-lg">{{ error }}</div>
        <button 
          @click="fetchCctvs"
          class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Coba Lagi
        </button>
      </div>

      <!-- CCTV List -->
      <div v-else-if="filteredCctvs.length > 0" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="cctv in filteredCctvs"
            :key="cctv.id"
            @click="goToDetail(cctv.id)"
            class="bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-md hover:border-blue-300 transition-all duration-200 cursor-pointer group"
          >
            <!-- Header with Camera Icon and Number -->
            <div class="bg-gray-50 px-4 py-3 rounded-t-xl border-b border-gray-100 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                  <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <span class="font-semibold text-gray-900">{{ getCameraNumber(cctv.type) }}</span>
              </div>
              
              <!-- Category Tag -->
              <span 
                v-if="cctv.category"
                :class="[
                  'px-2 py-1 text-xs font-medium rounded-full border',
                  getCategoryColor(cctv.category)
                ]"
              >
                {{ cctv.category }}
              </span>
            </div>

            <!-- Content -->
            <div class="p-4">
              <!-- Location Name -->
              <h3 class="font-semibold text-gray-900 text-lg mb-2 group-hover:text-blue-600 transition-colors">
                {{ cctv.location }}
              </h3>

              <!-- Coordinates if available -->
              <div v-if="formatCoordinates(cctv.coordinate)" class="flex items-center gap-2 mb-3 text-sm text-gray-600">
                <svg class="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd" />
                </svg>
                <span class="font-mono">{{ formatCoordinates(cctv.coordinate) }}</span>
              </div>

              <!-- Status -->
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 bg-green-500 rounded-full"></div>
                <span class="text-sm text-green-700 font-medium">Live Stream Available</span>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-4 py-3 bg-gray-50 rounded-b-xl border-t border-gray-100">
              <div class="flex items-center justify-between text-sm text-gray-600">
                <span>ID: {{ cctv.id.slice(0, 8) }}...</span>
                <div class="flex items-center gap-1 text-blue-600 group-hover:text-blue-700">
                  <span>Lihat Detail</span>
                  <svg class="w-4 h-4 transform group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-12">
        <div class="text-gray-500 text-lg">
          {{ searchQuery || selectedCategory !== 'all' ? 'Tidak ada kamera yang ditemukan' : 'Belum ada kamera yang tersedia' }}
        </div>
        <div v-if="searchQuery || selectedCategory !== 'all'" class="mt-4">
          <button 
            @click="searchQuery = ''; selectedCategory = 'all'"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Reset Filter
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom scrollbar for better UX */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* Smooth transitions */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 200ms;
}

/* Hover effects */
.group:hover .group-hover\:text-blue-600 {
  color: #2563eb;
}

.group:hover .group-hover\:text-blue-700 {
  color: #1d4ed8;
}

.group:hover .group-hover\:translate-x-1 {
  transform: translateX(0.25rem);
}
</style>
