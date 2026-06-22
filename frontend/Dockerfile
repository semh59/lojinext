# Frontend Dockerfile - Multi-stage Build
# ============================================================
# Stage 1: Build
# Base images digest-pinned (node:20-alpine, nginx:stable-alpine) — resolved 2026-06-17.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build-stage

WORKDIR /app

# Accept build-time API URL
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --no-fund

# Copy source code
COPY . .

# Generate API client from committed openapi.json (files are gitignored)
RUN npm run codegen

# Build the application
RUN npm run build

# ============================================================
# Stage 2: Serve with Nginx
FROM nginx:stable-alpine@sha256:5f979dcfed4ce6461873f087e8c980d6e29b084b9e8776d9704a7e989b5f4898 AS production-stage

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts from stage 1
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
