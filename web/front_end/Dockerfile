FROM node:22-alpine

WORKDIR /app

ENV VITE_SUPABASE_URL=https://oxftbkdevxewkvzsunuo.supabase.co
ENV VITE_SUPABASE_ANON_KEY=sb_publishable_TegSFZQvUkzULU8rFda1Kw_tIWMDhKO
ENV VITE_API_URL=https://01a0c9d9-f877-73c4-a505-60067dcbdc6c-8000.eur-1.aiven.app

COPY package*.json ./
RUN npm install

COPY . .

# Build assets ahead of time to eliminate in-memory bundling and avoid OOM SIGKILL
RUN npm run build

EXPOSE 3000
ENV PORT=3000

# Run lightweight preview server with minimal memory usage (<50MB)
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
