# Stage Pertama: Build aplikasi Vue.js
FROM node:22-alpine AS builder

WORKDIR /app

# Salin package.json dan package-lock.json untuk menginstal dependensi
COPY package.json package-lock.json ./
# Instal semua dependensi Node.js
RUN npm install

# Salin seluruh kode sumber frontend
COPY . .

# Build aplikasi Vue.js (output di folder /dist)
# Gunakan variabel lingkungan dari Docker Compose untuk API URL
# Perhatikan ini adalah bagian yang 'inject' variabel lingkungan ke Vue app saat build
ARG VITE_BACKEND_API_URL
ENV VITE_BACKEND_API_URL=${VITE_BACKEND_API_URL}
RUN npm run build


# Stage Kedua: Serve aplikasi menggunakan Nginx yang ringan
FROM nginx:alpine AS prod

# Hapus konfigurasi Nginx default
RUN rm /etc/nginx/conf.d/default.conf

# Salin hasil build dari builder stage ke direktori Nginx yang akan disajikan
COPY --from=builder /app/dist /usr/share/nginx/html

# Tambahkan konfigurasi Nginx kustom untuk serve SPA (Single Page Application)
# Ini penting agar routing di Vue.js bekerja dengan benar
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port Nginx
EXPOSE 80

# Command untuk menjalankan Nginx
CMD ["nginx", "-g", "daemon off;"]