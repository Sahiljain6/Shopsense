FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM node:22-alpine
RUN npm install -g serve@14
WORKDIR /app
COPY --from=build /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
