# One image for Render's free web service: build the React app, then serve it from FastAPI.
FROM node:20-bookworm-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY --from=web /src/frontend/dist /app/frontend/dist
WORKDIR /app/backend
EXPOSE 10000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
