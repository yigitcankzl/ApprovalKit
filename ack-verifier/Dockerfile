# ACK packages require Node >=22.
FROM node:22-alpine

WORKDIR /app

# Install deps first for layer caching.
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 8788

# Run TS directly via tsx — this is a small verification sidecar, no build step.
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
  CMD wget -qO- http://localhost:8788/health || exit 1

CMD ["npx", "tsx", "src/server.ts"]
