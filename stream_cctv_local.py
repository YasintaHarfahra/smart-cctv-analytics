import cv2
import sys

# Ganti dengan URL RTSP kamera Anda atau 0 untuk webcam
CCTV_STREAM_URL = "https://mam.jogjaprov.go.id:1937/cctv-bantul/TPRParangtritis.stream/chunklist_w307863718.m3u8"

# Fungsi untuk membuka stream video
def open_stream(url):
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print(f"ERROR: Gagal membuka stream video dari {url}")
        sys.exit(1)
    return cap

# Main function
def main():
    print(f"INFO: Mencoba membuka stream dari {CCTV_STREAM_URL}")
    cap = open_stream(CCTV_STREAM_URL)
    
    print("INFO: Stream berhasil dibuka. Menampilkan video. Tekan 'q' untuk keluar.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Gagal membaca frame dari stream.")
            cap.release()
            cap = open_stream(CCTV_STREAM_URL)
            continue
            
        cv2.imshow('Live CCTV Stream (Tekan q untuk Keluar)', frame)
        
        # Tekan tombol 'q' untuk keluar
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
