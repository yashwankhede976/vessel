# Frontend image (React + TypeScript, built with Vite, served by nginx).
# Build context is the repo root: docker build -f docker/frontend.Dockerfile .
# Deployed independently of the backend (static SPA).

# --- Build stage ---
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (better layer caching).
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copy source and build the production bundle.
COPY frontend/ ./
# VITE_API_BASE_URL is baked in at build time; override per environment.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# --- Runtime stage ---
FROM nginx:1.27-alpine AS runtime

# SPA routing: serve index.html for unknown routes.
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
