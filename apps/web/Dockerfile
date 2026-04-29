FROM node:22-alpine AS deps
WORKDIR /app
COPY apps/web/package.json ./
# Generate a fresh lockfile inside the image (host may not have pnpm).
RUN npm install --no-audit --no-fund

FROM node:22-alpine AS runner
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
EXPOSE 3000
CMD ["npm", "run", "dev"]
