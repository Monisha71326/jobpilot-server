# One image: builds the React app, then serves it plus the API from Django (gunicorn + whitenoise).
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN chmod +x entrypoint.sh && useradd -m app && mkdir -p media && chown -R app /app
USER app
EXPOSE 8000
CMD ["./entrypoint.sh"]
