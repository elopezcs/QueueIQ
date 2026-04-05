# QueueIQ Chatbot (RAG) – Local Setup Guide

This guide walks you through setting up the local environment required to run the QueueIQ Chatbot with Retrieval-Augmented Generation (RAG).

---

## 📋 Prerequisites

Before starting, make sure you have the following installed:

- Docker Desktop (running)
- PostgreSQL (for `psql` CLI tools)
- pgAdmin (optional but recommended)
- Ollama (for local LLM inference)

---

## ⚙️ Environment Setup

### 1. Add PostgreSQL to System Path

Ensure the following directory is added to your system environment variables:

C:\Program Files\PostgreSQL\18\bin

This allows you to use `psql` from the command line.

Optionally, ensure `psql.exe` is directly accessible:

C:\Program Files\PostgreSQL\18\bin\psql.exe

---

## 🐳 PostgreSQL + pgvector (Docker Setup)

### 2. Stop Existing Containers

From the project root:

docker compose down

---

### 3. Pull pgvector Image

docker pull pgvector/pgvector:pg18-trixie

---

### 4. Remove Existing Container (if any)

docker rm -f postgres-vector

---

### 5. Run PostgreSQL with pgvector

docker run -d ^
  --name postgres-vector ^
  -e POSTGRES_USER=postgres ^
  -e POSTGRES_PASSWORD=<YOUR_DB_PASSWORD> ^
  -e POSTGRES_DB=queueiq ^
  -p 5433:5432 ^
  pgvector/pgvector:pg18-trixie

This will start a PostgreSQL instance with pgvector enabled on port 5433.

---

## 🔌 Connect to Database (CLI)

psql -U postgres -h localhost -p 5433 -d queueiq

---

## 🧠 Enable pgvector Extension

Run the following inside `psql`:

CREATE EXTENSION vector;

SELECT * 
FROM pg_available_extensions 
WHERE name = 'vector';

---

## ✅ Verification

Run the following queries to confirm everything is working:

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

If this runs successfully, pgvector is correctly installed.

---

## 🖥️ pgAdmin Setup (Optional)

Register a new server in pgAdmin:

- Name: pgvector-docker
- Host: localhost
- Port: 5433
- Username: postgres
- Password: <YOUR_DB_PASSWORD>

---

## 🤖 Install and Configure Ollama

Ollama is used to run local LLMs for the chatbot.

### 1. Install Models

ollama pull gemma3:4b
ollama pull qwen2.5:7b

---

### 2. Verify Ollama is Running

You can test it with:

ollama run gemma3:4b

---

## 🚀 Next Steps

Once everything is installed:

1. Ensure your `.env` file points to the correct database:

DATABASE_URL=postgresql://postgres:<YOUR_DB_PASSWORD>@localhost:5433/queueiq

2. Start your backend:

docker compose up --build

3. Access the chatbot API (typically):

http://localhost:8000

---

## 🧩 Troubleshooting

### PostgreSQL Connection Issues

If you see:

connection refused localhost:5432

Make sure:
- You are using port 5433, not 5432
- Docker container is running:
  docker ps

---

### Docker Issues

To restart cleanly:

docker compose down -v
docker compose up --build

---

### Ollama Not Responding

Make sure Ollama is running locally and accessible:

http://localhost:11434

---

## 📌 Notes

- The system uses:
  - pgvector for semantic retrieval
  - PostgreSQL for structured data
  - Ollama for local LLM inference
- Ensure Docker Desktop is running before starting the system
- Avoid using localhost inside containers; use service names in Docker Compose if needed
