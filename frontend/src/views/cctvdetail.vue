<template>
  <div class="p-2 h-screen flex flex-col gap-0 relative">
    <!-- Bagian Atas: Video + Accuracy -->
    <div class="flex flex-1 gap-4 mb-0">
      <!-- Video CCTV (3/4) -->
      <button 
        class="px-3 py-1 rounded-md top-4 left-4 shadow-md h-[6vh] absolute z-50 bg-white" 
        @click="goBack"
      >
        ← Back
      </button>
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

      <!-- Vehicle Counts (1/4) -->
      <div class="flex-[1] max-h-[65vh] w-auto bg-white p-4 rounded-lg border overflow-y-auto relative">
        <h3 class="text-lg font-bold mb-3">Vehicle Counts</h3>
        <button @click="toggleDetection" :class="[ 'px-2 py-1 text-sm rounded absolute right-10 top-6 font-medium', isDetectionActive ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-green-500 text-white hover:bg-green-600' ]" > {{ isDetectionActive ? 'Stop Detection' : 'Start Detection' }} </button>
        <div class="space-y-3 mb-4">
          <div v-for="(count, vehicleType) in crossingCounts" :key="vehicleType" 
              class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div class="flex items-center gap-3">
              <span class="w-4 h-4 rounded-full" :style="{backgroundColor: getVehicleColor(vehicleType)}"></span>
              <span class="font-medium capitalize">{{ vehicleType }}</span>
            </div>
            <div class="text-right">
              <div class="text-lg font-bold">{{ count }}</div>
              <div class="text-xs text-gray-500">total crossed</div>
            </div>
          </div>
          <div v-if="Object.keys(crossingCounts).length === 0" class="text-sm text-gray-500">Belum ada hitungan.</div>
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
import { useRoute, useRouter } from 'vue-router'
import Hls from 'hls.js'

const route = useRoute()
const router = useRouter()
const cctv = ref({})
const videoPlayer = ref(null)
const detectionCanvas = ref(null)
let hls = null

// Object Detection State
const isDetectionActive = ref(false)
const wsStatus = ref('disconnected')
const detectedObjects = ref([])
const objectCounters = ref({})
const crossingCounts = ref({})
const isEditingLine = ref(false)
const virtualLine = ref([])
const allLines = ref([])
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

        // Network tolerances
        manifestLoadingTimeOut: 30000,
        levelLoadingTimeOut: 30000,
        fragLoadingTimeOut: 30000,
        manifestLoadingMaxRetry: 8,
        levelLoadingMaxRetry: 8,
        fragLoadingMaxRetry: 8,
        manifestLoadingRetryDelay: 1000,
        levelLoadingRetryDelay: 1000,
        fragLoadingRetryDelay: 1000,

        // Buffer & gap handling
        maxBufferLength: 6,
        maxMaxBufferLength: 30,
        maxBufferHole: 2,
        maxFragLookUpTolerance: 0.5,
        jumpLargeGaps: true,
        nudgeOffset: 0.4,
        nudgeMaxRetry: 10,

        // Live sync
        liveSyncDurationCount: 4,
        liveMaxLatencyDurationCount: 10,
        backBufferLength: 60,
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
        // Optional: manual start at live edge after manifest
        try { hls.autoStartLoad = false } catch(e) {}

        // setelah hls.attachMedia(video)
        hls.on(Hls.Events.ERROR, (event, data) => {
          console.error('HLS Error:', data);
          if (data.fatal) {
            switch (data.type) {
              case Hls.ErrorTypes.NETWORK_ERROR:
                hls.startLoad();
                break;
              case Hls.ErrorTypes.MEDIA_ERROR:
                hls.recoverMediaError();
                break;
              default:
                hls.destroy();
                break;
            }
          } else {
            // kalau bukan fatal (bufferStalledError dll.) coba startLoad & play ulang
            if (data.details === 'bufferStalledError') {
              try { hls.startLoad(); } catch(e) {}
              try { video.play().catch(()=>{}); } catch(e) {}
              // “nudge” currentTime supaya tidak macet
              try {
                const b = video.buffered;
                if (b.length > 0) {
                  const end = b.end(b.length - 1);
                  if (end - video.currentTime < 1) {
                    video.currentTime = end - 0.5;
                  }
                }
              } catch(e) {}
            }
          }
        });

        
        hls.on(Hls.Events.MEDIA_ATTACHED, () => {
          console.log("Media attached, ensuring source loaded...");
          try { hls.loadSource(url) } catch (e) { /* noop */ }
        });

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          console.log("Manifest parsed, starting playback...");
          try { hls.currentLevel = 0 } catch(e) {}
          try { hls.startLoad(-1) } catch(e) {}
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

        const tryNudge = () => {
          try {
            const ct = video.currentTime
            const b = video.buffered
            if (!b || b.length === 0) return
            const last = b.length - 1
            const start = b.start(0)
            const end = b.end(last)
            // Jika nyaris ke ujung buffer, loncat sedikit agar decoding lanjut
            if (end - ct < 1) {
              video.currentTime = Math.max(ct, end - 0.5)
            } else if (ct < start) {
              video.currentTime = start + 0.1
            }
          } catch (e) {}
        }

        hls.on(Hls.Events.ERROR, (event, data) => {
          console.error('HLS Error:', data);
          if (!data.fatal) {
            if (data.details === 'bufferStalledError' || data.details === 'fragLoadTimeOut') {
              try { hls.startLoad() } catch(e) {}
              try { video.play().catch(()=>{}) } catch(e) {}
              tryNudge()
            }
            return
          }
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              try { hls.startLoad() } catch(e) {}
              break
            case Hls.ErrorTypes.MEDIA_ERROR:
              try { hls.recoverMediaError() } catch(e) {}
              tryNudge()
              break
            default:
              reject(new Error('Fatal HLS error'))
          }
        });

        // Watchdog: periodically ensure we are near buffered range
        try {
          if (window._hlsStallWatch) clearInterval(window._hlsStallWatch)
          window._hlsStallWatch = setInterval(() => {
            try {
              if (!video || video.paused) return
              const rs = video.readyState
              const b = video.buffered
              if (!b || b.length === 0) return
              const last = b.length - 1
              const end = b.end(last)
              const ct = video.currentTime
              // if near end or readyState low, nudge to keep playing
              if (end - ct < 0.7 || rs < 3) {
                video.currentTime = Math.max(ct, end - 0.5)
              }
            } catch(e) { /* ignore */ }
          }, 2000)
        } catch(e) {}
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
      cctv.value = data.data || {}
      // Prefer single line sent by backend
      if (cctv.value && Array.isArray(cctv.value.line_points) && cctv.value.line_points.length >= 2) {
        virtualLine.value = cctv.value.line_points.slice(0,2)
        allLines.value = []
      } else {
        fetch(`/api/zones/${route.params.id}`)
          .then(r => r.json())
          .then(z => {
            if (z && Array.isArray(z.points) && z.points.length >= 2) {
              if (Array.isArray(z.points[0])) {
                const first = z.points.find(ln => Array.isArray(ln) && ln.length >= 2)
                if (first) virtualLine.value = first.slice(0,2)
              } else {
                virtualLine.value = z.points.slice(0,2)
              }
            }
          })
          .catch(() => {})
      }
      break
      
         case 'detection_results':
       console.log('Detection results received:', data.objects.length, 'objects')
       console.log('Sample object:', data.objects[0])
       
       detectedObjects.value = data.objects
       objectCounters.value = data.counters
       crossingCounts.value = data.crossing_counts || {}
       
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
  
  // Selalu bersihkan dan gambar ulang (agar garis tetap tampil walau objek 0)
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
  
  // Draw all virtual lines if exist
  const linesToDraw = (virtualLine.value.length === 2 ? [virtualLine.value] : [])
  for (const line of linesToDraw) {
    if (!Array.isArray(line) || line.length < 2) continue
    const p0 = line[0]
    const p1 = line[1]
    // Draw strictly horizontal line across full frame at the average Y
    const y = (p0.y + p1.y) * 0.5
    const xLeft = 0
    const xRight = videoWidth
    ctx.strokeStyle = '#00FFFF'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.moveTo(xLeft * (canvasWidth / videoWidth), y * (canvasHeight / videoHeight))
    ctx.lineTo(xRight * (canvasWidth / videoWidth), y * (canvasHeight / videoHeight))
    ctx.stroke()
  }
  
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
    
    // Optional: subtle confidence indicator (disabled to keep view clean)
    // If needed later, ensure to reset globalAlpha back to 1 after fill
    // ctx.fillStyle = obj.color
    // ctx.globalAlpha = 0.15
    // ctx.fillRect(scaledX, scaledY, scaledW, scaledH)
    ctx.globalAlpha = 1
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

const goBack = () => {
  // Navigate back to cctvlist with preserved query parameters
  const query = { ...route.query };
  
  // Ensure we have the scroll position
  if (!query.y) {
    query.y = String(window.scrollY || 0);
  }
  
  router.push({ 
    name: 'cctvlist', 
    query 
  });
};

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

    // Setup click handler for drawing line
    const canvas = detectionCanvas.value
    const video = videoPlayer.value
    if (canvas && video) {
      canvas.addEventListener('click', (e) => {
        if (!isEditingLine.value) return
        const rect = canvas.getBoundingClientRect()
        const px = e.clientX - rect.left
        const py = e.clientY - rect.top
        // Map from canvas to video pixel space
        const vx = (px / canvas.width) * (video.videoWidth || 640)
        const vy = (py / canvas.height) * (video.videoHeight || 360)
        if (virtualLine.value.length >= 2) virtualLine.value = []
        virtualLine.value.push({ x: vx, y: vy })
      })
    }
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
<script>
export default {
  methods: {
    startLineEdit() {
      this.$.setupState.isEditingLine = true
    },
    async saveLine() {
      this.$.setupState.isEditingLine = false
      const points = this.$.setupState.virtualLine
      if (!Array.isArray(points) || points.length < 2) return
      try {
        await fetch(`/api/zones/${this.$route.params.id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ camera_id: this.$route.params.id, points })
        })
      } catch (e) {
        console.warn('Failed to save line', e)
      }
    },
    clearLine() {
      this.$.setupState.virtualLine = []
      fetch(`/api/zones/${this.$route.params.id}`, { method: 'DELETE' }).catch(()=>{})
    }
  }
}
</script>