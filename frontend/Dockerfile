# Frontend image — multi-stage: build with Node, then serve static files with Nginx.

# ---- Stage 1: build the React app with Vite ----
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies first (better layer caching).
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest and build.
COPY . .

# VITE_API_URL is baked in at build time (Vite inlines env vars).
# docker-compose passes it in as a build arg; default is localhost for local runs.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- Stage 2: serve the built files with a tiny Nginx image ----
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
