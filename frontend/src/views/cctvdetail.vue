<template>
  <div class="p-4">
    <button class="px-3 py-1 mb-4 rounded border" @click="$router.back()">← Back</button>
    <div v-if="cctv && cctv.link">
      <h1 class="text-2xl font-bold mb-4">{{ cctv.location || cctv.name || 'CCTV' }}</h1>
      <div class="aspect-video bg-black">
        <video ref="videoPlayer" id="cctv-player" class="w-full h-full" controls autoplay muted playsinline></video>
      </div>
      <p class="mt-4">{{ cctv.description }}</p>
    </div>
    <div v-else>
      <p>Loading CCTV data...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import Hls from 'hls.js'

const route = useRoute()
const cctv = ref({})
const videoPlayer = ref(null) // ref untuk elemen video
let hls = null // Variabel untuk menyimpan instance HLS

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
    // Tunggu DOM merender ulang elemen <video> karena berada di bawah v-if="cctv.name"
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
        // Pastikan semua request HLS diarahkan via proxy agar tidak diblokir CORS
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

      // Ekspos instance untuk debugging dari Console
      window._hls = hls

      await new Promise((resolve, reject) => {
        video.addEventListener('loadedmetadata', () => {
          video.muted = true
          video.volume = 0
        }, { once: true })

        // Muat sumber sedini mungkin agar permintaan .m3u8 segera muncul
        try { hls.loadSource(url) } catch (e) { console.warn('Early loadSource failed', e) }

        hls.attachMedia(video);
        
        hls.on(Hls.Events.MEDIA_ATTACHED, () => {
          console.log("Media attached, ensuring source loaded...");
          try { hls.loadSource(url) } catch (e) { /* noop */ }
        });

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          console.log("Manifest parsed, starting playback...");
          // Perkuat autoplay: pastikan properti diset di runtime
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
              // Fallback: minta gesture user sekali untuk start
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
      // Fallback for Safari
      video.src = url;
      await video.play();
    } else {
      console.warn('HLS tidak didukung oleh browser ini dan fallback Safari tidak tersedia.')
      console.warn('Coba setel src langsung (non-HLS) jika URL bukan .m3u8')
    }
  } catch (error) {
    console.error("Error in loadAndPlayVideo:", error);
    throw error; // Re-throw the error to be handled by the caller
  }
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
  } catch (error) {
    console.error("Failed to initialize video:", error);
  }
});

onUnmounted(() => {
  if (hls) {
    console.log("Cleaning up HLS instance");
    hls.destroy();
    hls = null;
  }
});

watch(() => route.params.id, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    console.log("CCTV ID changed, loading new video...");
    try {
      await loadAndPlayVideo(newId);
    } catch (error) {
      console.error("Failed to load new video:", error);
    }
  }
});
</script>