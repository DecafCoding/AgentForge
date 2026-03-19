# =============================================================================
# Stage 1: Build — compile the React application
# =============================================================================
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests first for cache efficiency.
# This layer is invalidated only when package files change.
COPY package*.json ./
RUN npm ci

# Copy source and build the production bundle.
COPY . .
RUN npm run build

# =============================================================================
# Stage 2: Runtime — serve built assets with nginx
# =============================================================================
FROM nginx:alpine

# Copy built assets from the build stage.
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx config for SPA routing and API proxy.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
