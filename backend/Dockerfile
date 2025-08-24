# Gunakan image Python resmi
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies OS terlebih dahulu (supaya caching lebih efektif)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl\
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy hanya requirements.txt dulu (biar caching pip lebih efektif)
COPY requirements.txt .

# Install dependencies Python (gunakan cache biar lebih cepat)
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy semua source code ke container
COPY . .

# Expose port FastAPI (default: 8000)
EXPOSE 8000

# Jalankan aplikasi dengan Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
