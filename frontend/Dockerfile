FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* bun.lockb* ./
RUN npm ci

COPY . .

# Baked into the static bundle at build time (Vite env vars are compile-time).
# Set this as a Railway build variable pointing at the backend service's URL.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Railway assigns $PORT at runtime; nginx's docker-entrypoint auto-substitutes
# it into default.conf.template via envsubst before starting.
ENV PORT=8080
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
