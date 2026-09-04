# ---- deps: install once so source edits don't re-run npm ci ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

# ---- builder: compile the Next.js app ----
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so they
# have to be present now — the runtime env_file is too late for them. The .env
# files copied above are the source of truth; these ARGs let compose override a
# single value without editing .env (empty ARG = keep whatever .env says).
ARG NEXT_PUBLIC_API_URL=
ARG NEXT_PUBLIC_SUPABASE_URL=
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=
ARG NEXT_PUBLIC_VOICE_SERVICE_URL=
ARG NEXT_PUBLIC_VOICE_WS_URL=
# .env.production.local outranks .env in Next's env precedence, so only the
# non-empty overrides land there and the rest fall through to .env.
RUN for v in \
      "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL" \
      "NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL" \
      "NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY" \
      "NEXT_PUBLIC_VOICE_SERVICE_URL=$NEXT_PUBLIC_VOICE_SERVICE_URL" \
      "NEXT_PUBLIC_VOICE_WS_URL=$NEXT_PUBLIC_VOICE_WS_URL" \
    ; do [ -n "${v#*=}" ] && echo "$v" >> .env.production.local; done; true
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runner: standalone server only, no build tooling, no node_modules tree ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -g 1001 -S nodejs && adduser -u 1001 -S nextjs -G nodejs
# next build --output standalone traces only the files the server actually needs;
# public/ and .next/static are not traced and must be copied by hand.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
