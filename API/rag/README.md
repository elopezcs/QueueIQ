# QueueIQ Chatbot (RAG) – Local Setup Guide

This guide walks you through setting up the local environment required to run the QueueIQ Chatbot with Retrieval-Augmented Generation (RAG).

---

## 📋 Prerequisites

- Docker Desktop (running)
- PostgreSQL (for `psql` CLI tools)
- pgAdmin (optional but recommended)
- Ollama (for local LLM inference)

---

## ⚙️ Environment Setup

### 1. Add PostgreSQL to System Path

```bash
C:\Program Files\PostgreSQL\18\bin
```

Optional:

```bash
C:\Program Files\PostgreSQL\18\bin\psql.exe
```

---

## 🐳 PostgreSQL + pgvector (Docker Setup)

### 2. Stop Existing Containers

```bash
docker compose down
```

---

### 3. Pull pgvector Image

```bash
docker pull pgvector/pgvector:pg18-trixie
```

---

### 4. Remove Existing Container (if any)

```bash
docker rm -f postgres-vector
```

---

### 5. Run PostgreSQL with pgvector

#### Windows (CMD)

```bash
docker run -d ^
  --name postgres-vector ^
  -e POSTGRES_USER=postgres ^
  -e POSTGRES_PASSWORD=<YOUR_DB_PASSWORD> ^
  -e POSTGRES_DB=queueiq ^
  -p 5433:5432 ^
  pgvector/pgvector:pg18-trixie
```

#### macOS / Linux

```bash
docker run -d \
  --name postgres-vector \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=<YOUR_DB_PASSWORD> \
  -e POSTGRES_DB=queueiq \
  -p 5433:5432 \
  pgvector/pgvector:pg18-trixie
```

---

## 🔌 Connect to Database (CLI)

```bash
psql -U postgres -h localhost -p 5433 -d queueiq
```

---

## 🧠 Enable pgvector Extension

```sql
CREATE EXTENSION vector;

SELECT * 
FROM pg_available_extensions 
WHERE name = 'vector';
```

---

## ✅ Verification

```sql
SELECT version();

SELECT * 
FROM pg_available_extensions 
WHERE name = 'vector';

CREATE EXTENSION vector;

CREATE TABLE items (
  id bigserial PRIMARY KEY,
  embedding vector(3)
);

INSERT INTO items (embedding) 
VALUES ('[1,2,3]'), ('[4,5,6]');

SELECT * 
FROM items 
ORDER BY embedding <-> '[3,1,2]' 
LIMIT 5;
```

---

## 🖥️ pgAdmin Setup (Optional)

- Name: `pgvector-docker`
- Host: `localhost`
- Port: `5433`
- Username: `postgres`
- Password: `<YOUR_DB_PASSWORD>`

---

## 🤖 Install and Configure Ollama

### Install Models

```bash
ollama pull gemma3:4b
ollama pull qwen2.5:7b
```

---

### Verify Ollama

```bash
ollama run gemma3:4b
```

---

## 🚀 Required Bring-Up Steps (From Scratch)

Follow this exact order to avoid partial setup issues.

### 1) Configure Environment Variables

Set these in repo-root `.env`:

```bash
DATABASE_URL=postgresql://postgres:<YOUR_DB_PASSWORD>@localhost:5433/queueiq
# Optional explicit override (recommended for clarity):
RAG_DATABASE_URL=postgresql://postgres:<YOUR_DB_PASSWORD>@localhost:5433/queueiq

RAG_ENABLE_AUTO_INIT=true
RAG_MODEL_PROVIDER=ollama
RAG_ACTIVE_MODEL=gemma3_4b
RAG_OLLAMA_BASE_URL=http://127.0.0.1:11434
RAG_ENABLE_EMBEDDINGS=true
RAG_EMBEDDING_MODEL=nomic-embed-text
```

Notes:
- `DATABASE_URL` is required.
- `RAG_DATABASE_URL` is optional; if set, it takes precedence for RAG DB access.

---

### 2) Start QueueIQ

Use one startup path:

- Full local stack launcher:

```bash
.\.venv\Scripts\python.exe app.py
```

- Or backend only (for API testing):

```bash
.\.venv\Scripts\python.exe -m uvicorn API.main:app --host 127.0.0.1 --port 8000
```

At startup, QueueIQ auto-initializes RAG schema/tables in PostgreSQL when DB env vars are set.

---

### 3) Verify RAG Health

```bash
GET http://127.0.0.1:8000/rag/health
```

Expected:
- `"database_ready": true`
- `"pgvector_enabled": true` (or `false` if extension unavailable; lexical fallback still works)

---

### 4) Authenticate and Seed RAG Data (using tools such as Postman)

In non-dev, `POST /rag/seed` requires manager/staff auth.

Typical local flow :
1. (skip on Dev environment) `POST /auth/demo-login` with manager/staff demo email
2. (skip on Dev environment) Use returned bearer token
3. `POST /rag/seed`

---



### Access API

```bash
http://127.0.0.1:8000/docs
```

---

## 🧩 Troubleshooting

### Connection Refused

```bash
connection refused localhost:5432
```

Check:
- Use port `5433`
- Container is running:

```bash
docker ps
```

---

### Restart Docker Cleanly

```bash
docker compose down -v
docker compose up --build
```

---

### Ollama Not Responding

```bash
http://localhost:11434
```

---

## 📌 Notes

- Uses pgvector for semantic retrieval
- PostgreSQL for structured data
- Ollama for local LLM inference
- Ensure Docker Desktop is running
- Avoid using localhost inside containers
