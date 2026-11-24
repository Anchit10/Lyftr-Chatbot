# Backend image — multi-stage so the final runtime image stays small.

# ---- Stage 1: build/install dependencies into a clean prefix ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
# Install deps into /install so we can copy just that into the runtime stage.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: slim runtime image ----
FROM python:3.12-slim
WORKDIR /app

# Copy the installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy the application code.
COPY app ./app

# The SQLite database lives here, on a mounted volume (see docker-compose.yml),
# so history survives container restarts.
RUN mkdir -p /data

EXPOSE 8000

# Start the API. Host 0.0.0.0 so it is reachable from outside the container.
# Respect $PORT when the host injects one (Render, Railway, etc.); default to
# 8000 locally (docker-compose doesn't set PORT, so the mapping 8000:8000 holds).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
