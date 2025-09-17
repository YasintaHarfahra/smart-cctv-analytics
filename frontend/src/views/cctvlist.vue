<script setup>
import { ref, onMounted, computed, watch, nextTick, onUnmounted } from "vue";
import axios from "axios";
import { useRouter, useRoute } from "vue-router";
import bgImage from '../assets/bg.png'

const cctvs = ref([]);
const isLoading = ref(false);
const error = ref(null);
const router = useRouter();
const route = useRoute();
const searchQuery = ref("");
const selectedCategory = ref("all");
const scrollPosition = ref(0);

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json", Accept: "application/json" },
  // Prevent indefinite loading if backend is down or slow
  timeout: 8000,
});

const fetchCctvs = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    const res = await http.get("/cctv");
    cctvs.value = res.data.devices || [];   
  } catch (err) {
    console.error(err);
    if (err.code === 'ECONNABORTED') {
      error.value = "Permintaan timeout. Server lambat/tidak merespon.";
    } else if (err.response) {
      error.value = `Gagal memuat daftar CCTV (status ${err.response.status})`;
    } else {
      error.value = "Gagal memuat daftar CCTV. Periksa koneksi dan backend.";
    }
  } finally {
    isLoading.value = false;
  }
};

// Initialize filters from URL query and fetch data
onMounted(() => {
  // Read query params: q for search, cat for category, y for scroll position
  const { q, cat, y } = route.query || {};
  
  // Try to restore from URL first, then from localStorage
  if (typeof q === 'string') {
    searchQuery.value = q;
  } else {
    // Fallback to localStorage
    const savedSearch = localStorage.getItem('cctv_search_query');
    if (savedSearch) searchQuery.value = savedSearch;
  }
  
  if (typeof cat === 'string') {
    selectedCategory.value = cat;
  } else {
    // Fallback to localStorage
    const savedCategory = localStorage.getItem('cctv_selected_category');
    if (savedCategory) selectedCategory.value = savedCategory;
  }
  
  fetchCctvs().finally(async () => {
    // Try to restore scroll position from URL first, then from localStorage
    let scrollY = 0;
    if (typeof y === 'string') {
      scrollY = Number(y) || 0;
    } else {
      // Fallback to localStorage
      const savedScroll = localStorage.getItem('cctv_scroll_position');
      if (savedScroll) scrollY = Number(savedScroll) || 0;
    }
    
    if (scrollY > 0) {
      await nextTick();
      scrollPosition.value = scrollY;
      window.scrollTo({ top: scrollY, left: 0, behavior: 'auto' });
    }
  });
  
  // Add scroll event listener to track position
  window.addEventListener('scroll', handleScroll);
});

// Track scroll position
const handleScroll = () => {
  scrollPosition.value = window.scrollY;
  // Save scroll position to localStorage for persistence
  if (window.scrollY > 0) {
    localStorage.setItem('cctv_scroll_position', String(window.scrollY));
  }
};

// Keep URL query in sync with filters so state persists when navigating away/back
const syncQuery = () => {
  const query = { ...route.query };
  if (searchQuery.value) query.q = searchQuery.value; else delete query.q;
  if (selectedCategory.value && selectedCategory.value !== 'all') query.cat = selectedCategory.value; else delete query.cat;
  if (scrollPosition.value > 0) query.y = String(scrollPosition.value); else delete query.y;
  
  // Also save to localStorage as backup
  if (searchQuery.value) {
    localStorage.setItem('cctv_search_query', searchQuery.value);
  } else {
    localStorage.removeItem('cctv_search_query');
  }
  
  if (selectedCategory.value && selectedCategory.value !== 'all') {
    localStorage.setItem('cctv_selected_category', selectedCategory.value);
  } else {
    localStorage.removeItem('cctv_selected_category');
  }
  
  router.replace({ name: 'cctvlist', query });
};

watch([searchQuery, selectedCategory], syncQuery);

const goToDetail = (id) => {
  // carry current filters in query for consistency, plus current scroll Y
  const query = {};
  if (searchQuery.value) query.q = searchQuery.value;
  if (selectedCategory.value && selectedCategory.value !== 'all') query.cat = selectedCategory.value;
  query.y = String(scrollPosition.value || window.scrollY || 0);
  router.push({ name: "cctvdetail", params: { id }, query });
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
      return "bg-emerald-100 text-emerald-800 border-emerald-300 shadow-emerald-100";
    case "Perbatasan Kota":
      return "bg-amber-100 text-amber-800 border-amber-300 shadow-amber-100";
    case "Perbatasan Provinsi":
      return "bg-rose-100 text-rose-800 border-rose-300 shadow-rose-100";
    default:
      return "bg-slate-100 text-slate-800 border-slate-300 shadow-slate-100";
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

const clearFilters = () => {
  searchQuery.value = '';
  selectedCategory.value = 'all';
  // Clear localStorage
  localStorage.removeItem('cctv_search_query');
  localStorage.removeItem('cctv_selected_category');
  localStorage.removeItem('cctv_scroll_position');
};

onUnmounted(() => {
  // Remove scroll event listener
  window.removeEventListener('scroll', handleScroll);
  
  // Clear localStorage when leaving the page to prevent stale data
  // Only clear if no active filters
  if (!searchQuery.value && selectedCategory.value === 'all') {
    localStorage.removeItem('cctv_search_query');
    localStorage.removeItem('cctv_selected_category');
    localStorage.removeItem('cctv_scroll_position');
  }
});
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Header Section -->
    <div class="relative overflow-hidden min-h-screen">
      <!-- Background Pattern -->
      <div class="absolute inset-0 bg-cover bg-center opacity-80"
      :style="{ backgroundImage: `url(${bgImage})` }"></div>
      <div class="absolute inset-0 bg-gradient-to-b from-sky-600/80 via-indigo-600/80 to-slate-50 opacity-100"></div>
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_20px_20px,rgba(255,255,255,0.1)_1px,transparent_1px)] bg-[length:40px_40px] opacity-10"></div>
      
      <!-- Header Content -->
      <div class="relative z-10 bottom-0">
        <div class="container mx-auto px-4 py-4">
          <!-- Title and Icon Section -->
          <div class="flex justify-center mb-36 mt-48">
            <div class="flex items-center gap-3">
              <div class="w-40 h-40 bg-white/20 backdrop-blur-sm rounded-3xl flex items-center justify-center border border-white/30 flex-shrink-0">
                <svg class="w-32 h-32 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" 
                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div class="min-w-0 flex-1">
                <h1 class="text-xl lg:text-6xl font-bold text-white leading-tight">
                  Smart CCTV <br><span class="font-normal text-5xl">Analytics</span>
                </h1>
                <p class="text-white/90 text-sm mt-4 lg:text-base font-light leading-relaxed">
                  Monitor dan kelola semua kamera CCTV dengan teknologi AI
                </p>
              </div>
            </div>
          </div>
          <div class="px-10 py-3 lg:py-4">
            
            <!-- Stats and Actions Row -->
            <div class="flex flex-col lg:flex-row mb-6 gap-3 lg:gap-4">
              <!-- Stats Cards -->
              <div class="flex-1">
                <div class="grid grid-cols-3 gap-2 lg:gap-3">
                  <div class="rounded-xl p-3 lg:p-3 border border-white/30 bg-white/15 hover:bg-white/25 transition-colors duration-200 backdrop-blur-md text-white shadow-sm">
                    <div class="text-white/90 text-xs font-semibold mb-1">Total Kamera</div>
                    <div class="text-lg lg:text-xl font-bold">{{ cctvs.length }}</div>
                  </div>
                  <div class="rounded-xl p-3 lg:p-3 border border-white/30 bg-white/15 hover:bg-white/25 transition-colors duration-200 backdrop-blur-md text-white shadow-sm">
                    <div class="text-white/90 text-xs font-semibold mb-1">Aktif</div>
                    <div class="text-lg lg:text-xl font-bold text-emerald-300">{{ cctvs.length }}</div>
                  </div>
                  <div class="rounded-xl p-3 lg:p-3 border border-white/30 bg-white/15 hover:bg-white/25 transition-colors duration-200 backdrop-blur-md text-white shadow-sm">
                    <div class="text-white/90 text-xs font-semibold mb-1">Kategori</div>
                    <div class="text-lg lg:text-xl font-bold text-sky-200">{{ uniqueCategories.length }}</div>
                  </div>
                </div>
              </div>
            </div>
            <!-- Filters Section -->
            <div class="relative z-30 lg:-mt-2">
              <div class="container mx-auto">
                  <div class="flex flex-col lg:flex-row gap-3 lg:gap-4">
                    <!-- Search Input -->
                    <div class="flex-1 min-w-0">
                      <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-2 lg:pl-3 flex items-center pointer-events-none">
                          <svg class="h-3 lg:h-4 w-3 lg:w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                          </svg>
                        </div>
                        <input
                          v-model="searchQuery"
                          type="text"
                          placeholder="Cari berdasarkan lokasi, tipe kamera, atau kategori..."
                          class="block w-full pl-7 lg:pl-10 pr-2 lg:pr-3 py-2 lg:py-3 border border-gray-200 bg-gray-50/50 rounded-lg focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all duration-200 text-gray-900 placeholder-gray-500 text-xs lg:text-sm"
                        />
                      </div>
                    </div>
                    
                    <!-- Category Filter -->
                    <div class="w-full lg:w-48 flex-shrink-0">
                      <div class="relative">
                        <select
                          v-model="selectedCategory"
                          class="block w-full px-2 lg:px-3 py-2 lg:py-3 border border-gray-200 bg-gray-50/50 rounded-lg focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all duration-200 text-gray-900 appearance-none cursor-pointer text-xs lg:text-sm"
                        >
                          <option value="all">Semua Kategori</option>
                          <option v-for="category in uniqueCategories" :key="category" :value="category">
                            {{ category }}
                          </option>
                        </select>
                        <div class="absolute inset-y-0 right-0 flex items-center pr-2 lg:pr-3 pointer-events-none">
                          <svg class="h-3 lg:h-4 w-3 lg:w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Decorative Elements -->
      <div class="absolute top-0 right-0 w-24 lg:w-32 h-24 lg:h-32 bg-gradient-to-br from-white/10 to-transparent rounded-full blur-xl lg:blur-2xl animate-float"></div>
      <div class="absolute bottom-0 left-0 w-20 lg:w-32 h-20 lg:h-32 bg-gradient-to-tr from-purple-400/20 to-transparent rounded-full blur-lg lg:blur-xl animate-float" style="animation-delay: -3s;"></div>
    </div>

    <!-- Main Content -->
    <div class="container mx-auto px-12 py-4 lg:py-6">
      <!-- Loading State -->
      <div v-if="isLoading" class="flex justify-center items-center py-8 lg:py-12">
        <div class="relative">
          <div class="w-10 lg:w-12 h-10 lg:h-12 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin"></div>
          <div class="absolute inset-0 w-10 lg:w-12 h-10 lg:h-12 border-4 border-transparent border-t-sky-400 rounded-full animate-ping"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="text-center py-8 lg:py-12">
        <div class="bg-red-50 border border-red-200 rounded-xl p-4 lg:p-6 max-w-sm mx-auto">
          <div class="w-10 lg:w-12 h-10 lg:h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <svg class="w-5 lg:w-6 h-5 lg:h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="text-red-600 text-sm lg:text-base font-medium mb-3">{{ error }}</div>
          <button 
            @click="fetchCctvs"
            class="btn-modern px-3 lg:px-4 py-1.5 lg:py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors duration-200 font-medium text-xs lg:text-sm"
          >
            Coba Lagi
          </button>
        </div>
      </div>

      <!-- CCTV List -->
      <div v-else-if="filteredCctvs.length > 0" class="space-y-3 lg:space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 lg:gap-4">
          <div
            v-for="cctv in filteredCctvs"
            :key="cctv.id"
            @click="goToDetail(cctv.id)"
            class="group card-hover bg-white/80 backdrop-blur-sm rounded-xl shadow-md hover:shadow-lg border border-gray-100 hover:border-blue-300 transition-all duration-300 cursor-pointer"
          >
            <!-- Card Header with Gradient -->
            <div class="relative overflow-hidden rounded-t-xl">
              <div class="bg-gradient-to-r from-sky-500 to-indigo-600 px-3 lg:px-4 py-2 lg:py-3">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2 lg:gap-3 min-w-0">
                    <div class="w-6 lg:w-8 h-6 lg:h-8 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                      <svg class="w-3 lg:w-4 h-3 lg:h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div class="min-w-0">
                      <span class="text-white font-bold text-sm lg:text-base block truncate">{{ getCameraNumber(cctv.type) }}</span>
                      <div class="text-blue-100 text-xs truncate">Camera ID: {{ cctv.id.slice(0, 8) }}...</div>
                    </div>
                  </div>
                  
                  <!-- Status Indicator -->
                  <div class="flex items-center gap-1 lg:gap-2 flex-shrink-0">
                    <div class="w-2 lg:w-2.5 h-2 lg:h-2.5 bg-green-400 rounded-full animate-pulse"></div>
                    <span class="text-green-100 text-xs font-medium">Live</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Card Content -->
            <div class="p-3 lg:p-4">
              <!-- Location Name -->
              <h3 class="font-bold text-gray-900 text-base lg:text-lg mb-2 lg:mb-3 group-hover:text-sky-600 transition-colors duration-200 leading-tight">
                {{ cctv.location }}
              </h3>

              <!-- Category Tag - Moved here -->
              <div v-if="cctv.category" class="mb-2 lg:mb-3">
                <span 
                  :class="[
                    'inline-block px-2 lg:px-3 py-1 text-xs font-bold rounded-full border shadow-sm',
                    getCategoryColor(cctv.category)
                  ]"
                >
                  {{ cctv.category }}
                </span>
              </div>

              <!-- Camera Type -->
              <div class="flex items-center gap-2 mb-2 lg:mb-3 p-2 bg-gray-50 rounded-lg">
                <div class="w-5 lg:w-6 h-5 lg:h-6 bg-blue-100 rounded-md flex items-center justify-center flex-shrink-0">
                  <svg class="w-2.5 lg:w-3 h-2.5 lg:h-3 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <div class="min-w-0 flex-1">
                  <div class="text-xs text-gray-500 font-medium">Tipe Kamera</div>
                  <div class="text-xs text-gray-700 font-medium truncate">{{ cctv.type }}</div>
                </div>
              </div>
            </div>

            <!-- Card Footer -->
            <div class="px-3 lg:px-4 py-2 lg:py-3 bg-gray-50/50 rounded-b-xl border-t border-gray-100">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5 text-xs text-gray-600">
                  <svg class="w-3 h-3 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span>AI Detection Ready</span>
                </div>
                <div class="flex items-center gap-1 text-sky-600 group-hover:text-sky-700 font-medium text-xs">
                  <span>Lihat Detail</span>
                  <svg class="w-3 h-3 transform group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-8 lg:py-12">
        <div class="bg-white/80 backdrop-blur-sm rounded-xl p-6 lg:p-8 max-w-md mx-auto border border-gray-100 shadow-lg">
          <div class="w-12 lg:w-16 h-12 lg:h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3 lg:mb-4">
            <svg class="w-6 lg:w-8 h-6 lg:h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <div class="text-gray-600 text-sm lg:text-base font-medium mb-3 lg:mb-4">
            {{ searchQuery || selectedCategory !== 'all' ? 'Tidak ada kamera yang ditemukan' : 'Belum ada kamera yang tersedia' }}
          </div>
          <div v-if="searchQuery || selectedCategory !== 'all'" class="mt-3 lg:mt-4">
            <button 
              @click="clearFilters"
              class="btn-modern px-3 lg:px-4 py-1.5 lg:py-2 bg-gradient-to-r from-sky-600 to-indigo-600 text-white rounded-lg hover:from-sky-700 hover:to-indigo-700 transition-all duration-200 font-medium shadow-md hover:shadow-lg text-xs lg:text-sm"
            >
              Reset Filter
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom scrollbar for better UX */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f8fafc;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: linear-gradient(to bottom, #3b82f6, #6366f1);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(to bottom, #2563eb, #4f46e5);
}

/* Smooth transitions */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 300ms;
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

/* Custom animations */
@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
}

@keyframes pulse-glow {
  0%, 100% { 
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
  }
  50% { 
    box-shadow: 0 0 30px rgba(59, 130, 246, 0.6);
  }
}

/* Floating animation for decorative elements */
.animate-float {
  animation: float 6s ease-in-out infinite;
}

/* Pulse glow for interactive elements */
.animate-pulse-glow {
  animation: pulse-glow 2s ease-in-out infinite;
}

/* Glass morphism effect */
.glass {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Gradient text */
.gradient-text {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Card hover effects */
.card-hover {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-hover:hover {
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

/* Button hover effects */
.btn-modern {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.btn-modern::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.btn-modern:hover::before {
  left: 100%;
}

.btn-modern:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
}

/* Fix for stacking issues */
.container {
  position: relative;
  z-index: 1;
}

/* Ensure proper grid behavior */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

@media (min-width: 768px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1280px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Prevent text overflow */
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Ensure cards don't stack */
.group {
  position: relative;
  z-index: 1;
}

/* Fix for backdrop blur issues */
.backdrop-blur-sm {
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.backdrop-blur-xl {
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

/* Ensure proper spacing */
.gap-3 > * + * {
  margin-left: 0.75rem;
}

.gap-4 > * + * {
  margin-left: 1rem;
}

/* Fix for flexbox issues */
.flex-1 {
  flex: 1 1 0%;
}

.flex-shrink-0 {
  flex-shrink: 0;
}

/* Ensure proper positioning */
.relative {
  position: relative;
}

.absolute {
  position: absolute;
}

/* Fix for z-index stacking */
.z-10 {
  z-index: 10;
}

.z-20 {
  z-index: 20;
}
</style>
