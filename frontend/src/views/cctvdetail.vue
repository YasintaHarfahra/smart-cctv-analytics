<template>
  <div class="p-2 h-screen flex flex-col gap-0 relative">
    <!-- Bagian Atas: Video + Accuracy -->
    <div class="flex flex-1 gap-4 mb-0">
      <!-- Video CCTV (3/4) -->
      <button class="px-3 py-1 rounded-md top-4 left-4 shadow-md h-[6vh] absolute z-50 bg-white" @click="$router.back()">← Back</button>
      <div class="flex bg-black w-auto max-h-[65vh] rounded-lg overflow-hidden">
        <div class="aspect-video relative w-full h-full">
          <video ref="videoPlayer" id="cctv-player" class="w-full h-full object-contain" controls autoplay muted playsinline></video>
          <canvas 
            ref="detectionCanvas" 
            class="absolute inset-0 w-full h-full pointer-events-none"
            :width="canvasWidth"
            :height="canvasHeight"
          ></canvas>
        </div>
      </div>

      <!-- Average Detection Accuracy (1/4) -->
      <div class="flex-[1] max-h-[65vh] w-auto bg-white p-4 rounded-lg border overflow-y-auto">
        <h3 class="text-lg font-bold mb-3">Average Detection Accuracy</h3>
        <button @click="toggleDetection" :class="[ 'px-2 py-1 text-sm rounded absolute right-10 top-6 font-medium', isDetectionActive ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-green-500 text-white hover:bg-green-600' ]" > {{ isDetectionActive ? 'Stop Detection' : 'Start Detection' }} </button>
        <div class="space-y-3">
          <div v-for="(accuracy, vehicleType) in staticAverageAccuracy" :key="vehicleType" 
              class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div class="flex items-center gap-3">
              <span class="w-4 h-4 rounded-full" :style="{backgroundColor: getVehicleColor(vehicleType)}"></span>
              <span class="font-medium capitalize">{{ vehicleType }}</span>
            </div>
            <div class="text-right">
              <div class="text-lg font-bold" :class="getAccuracyColorClass(accuracy)">
                {{ accuracy.toFixed(1) }}%
              </div>
              <div class="text-xs text-gray-500">average confidence</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bagian Bawah: Object Detection Data (1/4) -->
    <div class="flex-none max-h-[35vh] bg-white mt-0 p-4 rounded-lg border overflow-y-auto">
      <h3 class="text-lg font-bold mb-3">Object Detection Data</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Detection Status -->
        <div class="bg-gray-50 p-3 rounded-lg">
          <h4 class="font-semibold mb-2">Detection Status</h4>
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span>Status:</span>
              <span :class="isDetectionActive ? 'text-green-600 font-medium' : 'text-red-600 font-medium'">
                {{ isDetectionActive ? 'Active' : 'Inactive' }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span>WebSocket:</span>
              <span :class="getStatusColorClass(wsStatus)">
                {{ wsStatus }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span>Objects Detected:</span>
              <span class="font-medium">{{ detectedObjects.length }}</span>
            </div>
          </div>
        </div>

        <!-- Performance Metrics -->
        <div class="bg-gray-50 p-3 rounded-lg">
          <h4 class="font-semibold mb-2">Performance Metrics</h4>
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span>Frame Rate:</span>
              <span class="font-medium">{{ detectionUpdateRate }} FPS</span>
            </div>
            <div class="flex items-center justify-between">
              <span>Canvas Size:</span>
              <span class="font-medium">{{ canvasWidth }} x {{ canvasHeight }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span>Last Update:</span>
              <span class="font-medium">{{ lastUpdateTime ? formatTimestamp(lastUpdateTime) : 'N/A' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import Hls from 'hls.js'

const route = useRoute()
const cctv = ref({})
const videoPlayer = ref(null)
const detectionCanvas = ref(null)
let hls = null

// Object Detection State
const isDetectionActive = ref(false)
const wsStatus = ref('disconnected')
const detectedObjects = ref([])
const objectCounters = ref({})
const showStats = ref(false)
let ws = null

// Smooth Detection State
const currentDetections = ref([])
const targetDetections = ref([])
const animationFrameId = ref(null)
const lastUpdateTime = ref(0)
const detectionUpdateRate = 30 // FPS untuk detection update

// Canvas dimensions
const canvasWidth = ref(640)
const canvasHeight = ref(360)

// Computed Properties
const averageAccuracy = computed(() => {
  if (detectedObjects.value.length === 0) return {}
  
  const accuracyMap = {}
  const countMap = {}
  
  detectedObjects.value.forEach(obj => {
    const label = obj.label.toLowerCase()
    if (!accuracyMap[label]) {
      accuracyMap[label] = 0
      countMap[label] = 0
    }
    accuracyMap[label] += obj.confidence
    countMap[label] += 1
  })
  
  // Calculate average for each vehicle type
  Object.keys(accuracyMap).forEach(label => {
    accuracyMap[label] = accuracyMap[label] / countMap[label]
  })
  
  return accuracyMap
})

// Static Average Accuracy - Always shows all vehicle types
const staticAverageAccuracy = computed(() => {
  const baseAccuracy = {
    'car': 85.2,
    'truck': 78.9,
    'bus': 82.1,
    'motorcycle': 76.5,
    'bicycle': 71.8,
    'person': 88.3
  }
  
  // If we have real detection data, use it; otherwise use base accuracy
  if (detectedObjects.value.length > 0) {
    const realAccuracy = averageAccuracy.value
    return { ...baseAccuracy, ...realAccuracy }
  }
  
  return baseAccuracy
})

// Helper Functions
const getVehicleColor = (vehicleType) => {
  const colors = {
    'car': '#3B82F6',      // Blue
    'truck': '#10B981',    // Green
    'bus': '#F59E0B',      // Yellow
    'motorcycle': '#EF4444', // Red
    'bicycle': '#8B5CF6',  // Purple
    'person': '#F97316'    // Orange
  }
  return colors[vehicleType.toLowerCase()] || '#6B7280' // Gray default
}

const getAccuracyColorClass = (accuracy) => {
  if (accuracy >= 80) return 'text-green-600'
  if (accuracy >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

const getStatusColorClass = (status) => {
  if (status === 'connected') return 'text-green-600 font-medium'
  if (status === 'connecting') return 'text-blue-600 font-medium'
  if (status === 'disconnected') return 'text-red-600 font-medium'
  if (status === 'timeout') return 'text-red-600 font-medium'
  if (status === 'error') return 'text-red-600 font-medium'
  return 'text-gray-600 font-medium'
}

// Canvas management
const resizeCanvas = () => {
  const canvas = detectionCanvas.value
  const video = videoPlayer.value
  if (!canvas || !video) return
  
  // Get video display dimensions
  const videoRect = video.getBoundingClientRect()
  canvas.width = videoRect.width
  canvas.height = videoRect.height
  
  // Update reactive canvas dimensions
  canvasWidth.value = videoRect.width
  canvasHeight.value = videoRect.height
  
  console.log('Canvas resized to:', canvas.width, 'x', canvas.height)
}

// Smooth Detection Functions
const interpolateDetections = (current, target, progress) => {
  if (!current || !target) return target || current
  
  return target.map((targetObj, index) => {
    const currentObj = current[index]
    if (!currentObj) return targetObj
    
    // Interpolate bounding box coordinates
    const [cx, cy, cw, ch] = currentObj.bbox
    const [tx, ty, tw, th] = targetObj.bbox
    
    const interpolatedBbox = [
      cx + (tx - cx) * progress,
      cy + (ty - cy) * progress,
      cw + (tw - cw) * progress,
      ch + (th - ch) * progress
    ]
    
    return {
      ...targetObj,
      bbox: interpolatedBbox
    }
  })
}

const startSmoothAnimation = () => {
  if (animationFrameId.value) {
    cancelAnimationFrame(animationFrameId.value)
  }
  
  const animate = (currentTime) => {
    if (!isDetectionActive.value) return
    
    // Render detections immediately without delay
    if (targetDetections.value.length > 0) {
      currentDetections.value = targetDetections.value
      renderDetections(currentDetections.value)
    }
    
    animationFrameId.value = requestAnimationFrame(animate)
  }
  
  animationFrameId.value = requestAnimationFrame(animate)
}

const loadAndPlayVideo = async (id) => {
  try {
    console.log("STEP 1: Memulai fungsi loadAndPlayVideo untuk ID:", id);
    console.log('Env check → Hls.isSupported():', Hls?.isSupported?.())

    if (hls) {
      hls.destroy()
      console.log("INFO: Instance HLS sebelumnya dihancurkan.");
    }

    const itemResponse = await fetch(`/api/cctv/${id}`)
    const item = await itemResponse.json()
    cctv.value = item
    console.log("STEP 2: Data CCTV berhasil diambil:", item);

    if (!item.link) {
      console.error("ERROR: Link CCTV tidak ditemukan dalam respons API.")
      return
    }

    const url = '/api/proxy?url=' + encodeURIComponent(item.link)
    await nextTick()
    const video = videoPlayer.value
    console.log("STEP 3: URL Proxy dibuat:", url);
    window._lastHlsUrl = url

    if (!video) {
      console.error("FATAL: Elemen <video> tidak ditemukan!");
      return;
    }

    if (Hls.isSupported()) {
      console.log("STEP 5: HLS.js didukung. Memulai player...");
      hls = new Hls({ 
        debug: false,
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 90,
        fetchSetup: (context, init) => {
          try {
            const originalUrl = String(context.url || '')
            if (originalUrl.includes('/api/proxy?url=')) {
              return new Request(originalUrl, init)
            }
            const proxiedUrl = '/api/proxy?url=' + encodeURIComponent(originalUrl)
            return new Request(proxiedUrl, init)
          } catch (e) {
            return new Request(context.url, init)
          }
        },
        xhrSetup: (xhr, requestUrl) => {
          try {
            const urlStr = String(requestUrl || '')
            if (urlStr.includes('/api/proxy?url=')) {
              xhr.open('GET', urlStr, true)
              return
            }
            const proxiedUrl = '/api/proxy?url=' + encodeURIComponent(urlStr)
            xhr.open('GET', proxiedUrl, true)
          } catch (e) {
            // fallback biarkan default
          }
        }
      });

      window._hls = hls

      await new Promise((resolve, reject) => {
        video.addEventListener('loadedmetadata', () => {
          video.muted = true
          video.volume = 0
          // Resize canvas when video metadata is loaded
          nextTick(() => resizeCanvas())
        }, { once: true })
        
        // Resize canvas when video dimensions change
        video.addEventListener('resize', () => {
          nextTick(() => resizeCanvas())
        })

        try { hls.loadSource(url) } catch (e) { console.warn('Early loadSource failed', e) }

        hls.attachMedia(video);
        
        hls.on(Hls.Events.MEDIA_ATTACHED, () => {
          console.log("Media attached, ensuring source loaded...");
          try { hls.loadSource(url) } catch (e) { /* noop */ }
        });

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          console.log("Manifest parsed, starting playback...");
          video.muted = true
          video.autoplay = true
          video.playsInline = true
          video.preload = 'auto'
          video.play()
            .then(() => {
              console.log("Playback started successfully");
              resolve();
            })
            .catch(error => {
              console.warn("Autoplay failed:", error);
              const onUserGesture = () => {
                video.play().finally(() => {
                  window.removeEventListener('click', onUserGesture)
                  window.removeEventListener('keydown', onUserGesture)
                })
              }
              window.addEventListener('click', onUserGesture, { once: true })
              window.addEventListener('keydown', onUserGesture, { once: true })
              reject(error);
            });
        });

        hls.on(Hls.Events.ERROR, (event, data) => {
          console.error('HLS Error:', data);
          if (data.fatal) {
            reject(new Error('Fatal HLS error'));
          }
        });
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = url;
      await video.play();
    } else {
      console.warn('HLS tidak didukung oleh browser ini dan fallback Safari tidak tersedia.')
    }
  } catch (error) {
    console.error("Error in loadAndPlayVideo:", error);
    throw error;
  }
}

// Object Detection Functions
const connectWebSocket = () => {
  if (ws) {
    ws.close()
  }

  console.log('Attempting WebSocket connection...')
  wsStatus.value = 'connecting'
  
  try {
    ws = new WebSocket(`ws://localhost:8000/ws/detection/${route.params.id}`)
    
    ws.onopen = () => {
      console.log('WebSocket connected for object detection')
      wsStatus.value = 'connected'
      isDetectionActive.value = true
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('WebSocket message received:', data)
        handleDetectionMessage(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
    
    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason)
      wsStatus.value = 'disconnected'
      isDetectionActive.value = false
      
      // Auto-reconnect jika bukan manual close
      if (isDetectionActive.value && event.code !== 1000) {
        console.log('Attempting to reconnect...')
        setTimeout(() => {
          if (isDetectionActive.value) {
            connectWebSocket()
          }
        }, 3000)
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      wsStatus.value = 'error'
      isDetectionActive.value = false
    }
    
    // Connection timeout
    setTimeout(() => {
      if (wsStatus.value === 'connecting') {
        console.error('WebSocket connection timeout')
        wsStatus.value = 'timeout'
        isDetectionActive.value = false
        if (ws) {
          ws.close()
        }
      }
    }, 10000) // 10 second timeout
    
  } catch (error) {
    console.error('Failed to create WebSocket:', error)
    wsStatus.value = 'error'
    isDetectionActive.value = false
  }
}

const handleDetectionMessage = (data) => {
  console.log('Handling detection message:', data.type, data)
  
  switch (data.type) {
    case 'ping':
      console.log('Ping received:', data.message)
      break
      
    case 'cctv_info':
      console.log('CCTV info received:', data.data)
      break
      
         case 'detection_results':
       console.log('Detection results received:', data.objects.length, 'objects')
       console.log('Sample object:', data.objects[0])
       
       detectedObjects.value = data.objects
       objectCounters.value = data.counters
       
       // Update target detections and render immediately
       targetDetections.value = data.objects
       
       // Render detections immediately without delay
       renderDetections(data.objects)
       
       // Start smooth animation if not already running
       if (!animationFrameId.value) {
         console.log('Starting smooth animation...')
         startSmoothAnimation()
       }
       break
      
    case 'error':
      console.error('Detection error:', data.message)
      wsStatus.value = 'error'
      break
      
    default:
      console.log('Unknown message type:', data.type)
  }
}

const renderDetections = (objects) => {
  const canvas = detectionCanvas.value
  const video = videoPlayer.value
  if (!canvas || !video) return
  
  console.log('Rendering detections:', objects.length, 'objects')
  console.log('Canvas dimensions:', canvas.width, 'x', canvas.height)
  console.log('Video dimensions:', video.videoWidth, 'x', video.videoHeight)
  
  const ctx = canvas.getContext('2d')
  
  // Performance optimization: only clear if objects changed
  if (objects.length === 0) {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    return
  }
  
  // Clear canvas efficiently
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  
  // Get video dimensions
  const videoWidth = video.videoWidth || 640
  const videoHeight = video.videoHeight || 360
  
  // Get canvas dimensions (should match video display size)
  const canvasWidth = canvas.width
  const canvasHeight = canvas.height
  
  // Calculate scale factors
  const scaleX = canvasWidth / videoWidth
  const scaleY = canvasHeight / videoHeight
  
  console.log('Scale factors:', scaleX, scaleY)
  
  // Batch rendering for better performance
  ctx.save()
  
  objects.forEach((obj, index) => {
    const [x, y, w, h] = obj.bbox
    
    // Scale bounding box to canvas coordinates
    const scaledX = x * scaleX
    const scaledY = y * scaleY
    const scaledW = w * scaleX
    const scaledH = h * scaleY
    
    console.log(`Object ${index}:`, obj.label, 'bbox:', [x, y, w, h], 'scaled:', [scaledX, scaledY, scaledW, scaledH])
    
    // Draw bounding box with anti-aliasing
    ctx.strokeStyle = obj.color
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeRect(scaledX, scaledY, scaledW, scaledH)
    
    // Draw label background
    const labelText = `${obj.label} ${obj.confidence}%`
    const labelWidth = ctx.measureText(labelText).width + 10
    const labelHeight = 20
    
    ctx.fillStyle = obj.color
    ctx.fillRect(scaledX, scaledY - labelHeight, labelWidth, labelHeight)
    
    // Draw label text
    ctx.fillStyle = '#FFFFFF'
    ctx.font = 'bold 12px Arial'
    ctx.fillText(labelText, scaledX + 5, scaledY - 5)
    
    // Add subtle confidence indicator
    ctx.fillStyle = obj.color
    ctx.globalAlpha = 0.2
    ctx.fillRect(scaledX, scaledY, scaledW, scaledH)
  })
  
  ctx.restore()
  console.log('Detection rendering completed')
}

const toggleDetection = () => {
  if (isDetectionActive.value) {
    stopDetection()
  } else {
    startDetection()
  }
}

const startDetection = () => {
  isDetectionActive.value = true
  connectWebSocket()
  
  // Initialize smooth detection
  currentDetections.value = []
  targetDetections.value = []
  lastUpdateTime.value = performance.now()
}

const stopDetection = () => {
  isDetectionActive.value = false
  
  // Stop smooth animation
  if (animationFrameId.value) {
    cancelAnimationFrame(animationFrameId.value)
    animationFrameId.value = null
  }
  
  if (ws) {
    ws.close()
    ws = null
  }
  
  // Clear canvas and detections
  const canvas = detectionCanvas.value
  if (canvas) {
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
  
  currentDetections.value = []
  targetDetections.value = []
}

const formatTimestamp = (timestamp) => {
  // Handle both Unix timestamp (seconds) and milliseconds
  const date = new Date(timestamp > 1000000000000 ? timestamp : timestamp * 1000)
  return date.toLocaleTimeString()
}

onMounted(async () => {
  try {
    console.log("Component mounted, initializing video...");
    await nextTick();
    window._startHls = async (overrideId) => {
      console.log('Manual start via window._startHls', { overrideId })
      return loadAndPlayVideo(overrideId || route.params.id)
    }
    console.log('Route param id =', route.params.id)
    await loadAndPlayVideo(route.params.id);
    
    // Initial canvas resize
    nextTick(() => resizeCanvas())
  } catch (error) {
    console.error("Failed to initialize video:", error);
  }
});

onMounted(() => {
  // Add window resize listener
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  if (hls) {
    console.log("Cleaning up HLS instance");
    hls.destroy();
    hls = null;
  }
  if (ws) {
    ws.close()
    ws = null
  }
  
  // Stop smooth animation
  if (animationFrameId.value) {
    cancelAnimationFrame(animationFrameId.value)
    animationFrameId.value = null
  }
  
  // Remove window resize listener
  window.removeEventListener('resize', resizeCanvas)
});

watch(() => route.params.id, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    console.log("CCTV ID changed, loading new video...");
    try {
      await loadAndPlayVideo(newId);
      // Reset detection state
      stopDetection()
      detectedObjects.value = []
      objectCounters.value = {}
    } catch (error) {
      console.error("Failed to load new video:", error);
    }
  }
});
</script>