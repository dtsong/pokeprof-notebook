FROM node:20-bookworm-slim AS frontend

WORKDIR /app/frontend

COPY frontend/package.json ./

# No lockfile committed yet; use npm install.
RUN npm install

COPY frontend/ ./

# Vite env vars are compile-time. These are NOT secrets.
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_APP_ID

ENV VITE_FIREBASE_API_KEY=${VITE_FIREBASE_API_KEY} \
    VITE_FIREBASE_AUTH_DOMAIN=${VITE_FIREBASE_AUTH_DOMAIN} \
    VITE_FIREBASE_PROJECT_ID=${VITE_FIREBASE_PROJECT_ID} \
    VITE_FIREBASE_APP_ID=${VITE_FIREBASE_APP_ID}

RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY data/indexes/ ./data/indexes/
COPY --from=frontend /app/frontend/build/ ./frontend/build/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn pokeprof_notebook.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
