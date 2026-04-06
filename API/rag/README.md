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

## 🚀 Next Steps

### Configure `.env`

```bash
DATABASE_URL=postgresql://postgres:<YOUR_DB_PASSWORD>@localhost:5433/queueiq
```

### Start Backend

```bash
docker compose up --build
```

### Access API

```bash
http://localhost:8000
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
