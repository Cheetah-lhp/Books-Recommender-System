FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_URL=

ENV VITE_API_URL=${VITE_API_URL}

COPY package*.json ./
RUN npm ci || npm install

COPY . .
RUN npm run build

FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

COPY --from=build /app/.output ./.output
COPY --from=build /app/package.json ./package.json

EXPOSE 3000

# Nitro / TanStack Start production server — NOT vite preview
CMD ["node", ".output/server/index.mjs"]
