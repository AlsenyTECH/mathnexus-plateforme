# Construit l'application, puis la sert avec Caddy, qui relaie /api et /gestion vers Django.
FROM node:22-alpine AS construction
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=construction /app/dist /srv
