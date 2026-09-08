# Production image for the Next.js frontend.
# Previously this image ran `npm run dev` (the development server) and installed
# with `npm install` while package-lock.json was never copied, so builds were
# neither reproducible nor production-grade.

# ---- deps: install exactly what the lockfile pins ----------------------------
FROM node:18-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- builder: produce the optimized production build ------------------------
FROM node:18-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so the
# API base URL must be supplied here as a build argument. Setting it only as a
# runtime `environment:` entry has no effect on a production build.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runner: production dependencies only -----------------------------------
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# Install production dependencies only; dev dependencies (typescript, @types/*)
# are build-time tools and must not ship in the runtime image.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./next.config.js

# Run as the unprivileged user that the node images already provide.
RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["npm", "run", "start"]
