FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
# next.config.js sets output: "export" — this produces static HTML/JS in ./out,
# the same artifact CI syncs to S3/CloudFront in production. Serving that same
# output locally (instead of a Node SSR server) keeps local docker-compose
# faithful to how the app actually runs once deployed.
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN npm install -g serve@14
COPY --from=builder /app/out ./out

EXPOSE 3000
CMD ["serve", "-s", "out", "-l", "3000"]
