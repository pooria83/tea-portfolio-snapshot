ARG PORT=3000

FROM node:24-slim AS deps
ARG PORT
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --only=production --ignore-scripts

FROM deps AS dev
ARG PORT
COPY . .
EXPOSE $PORT
ENV NODE_ENV=development PORT=$PORT
USER 1000
CMD ["sh", "-c", "npm run dev"]

FROM node:24-slim AS build
ARG PORT
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID
ARG GIT_SHA=unknown
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID GIT_SHA=$GIT_SHA
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

FROM node:24-slim AS production
ARG PORT
ARG GIT_SHA=unknown
WORKDIR /app
ENV NODE_ENV=production PORT=$PORT GIT_SHA=$GIT_SHA
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=deps /app/node_modules node_modules
COPY --from=build /app/.next .next
COPY --from=build /app/public public
COPY --from=build /app/next.config.ts .
COPY --from=build /app/package.json .
RUN mkdir -p /app/.next/cache/images && chown 1000:1000 /app/.next/cache/images
EXPOSE $PORT
USER 1000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:$PORT/api/health || exit 1
CMD ["sh", "-c", "npm run start"]
