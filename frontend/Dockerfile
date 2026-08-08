# TrustShield frontend — Node 18 + Next.js 14 production
FROM node:18-alpine

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
COPY frontend/.npmrc ./
RUN npm install --include=dev

COPY frontend/ .
RUN npm run build

EXPOSE 3000
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
CMD ["npm", "start"]
