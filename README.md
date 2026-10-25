# ShopSmart AI

A full-stack AI-assisted storefront built to implement the four workflows in the supplied system-design README: shopping and checkout, safe hybrid product search, policy ingestion, and grounded policy Q&A. The hackathon use case additionally calls for product discovery, comparison, wishlist, authentication, and order tracking.

## Stack

- **Client:** React + Vite, Lucide icons
- **Server:** FastAPI, SQLAlchemy, SQLite, JWT
- **AI:** LangChain with Groq (`llama-3.3-70b-versatile` by default), configurable through environment variables
- **Retrieval:** ChromaDB with independent `product_vectors` and `policy_documents` collections

The catalog and policy corpus work when Groq is not configured, using deterministic fallback behavior. AI product search uses a validated query plan and parameterized SQL filters; SQLite remains authoritative for price and stock. Chroma policy retrieval and uploads use a separate collection. Checkout revalidates stock and writes orders, line items, stock updates, and tracking events in one database transaction. Payment is simulated.

## Run locally

Requirements: Python 3.11+ and Node.js 20+.

### API

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Add your GROQ_API_KEY to .env to enable Groq responses
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### Client

```powershell
cd client
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173. The backend seeds sample categories, 69 products across 21 categories, five policy records, and a demo customer on first run. The AI assistant uses Groq; set `GROQ_API_KEY` in `server/.env` before starting the backend.

**Demo login:** `demo@shopsmart.ai` / `ShopSmart123!`

## Features

- Product catalog, text search, category selection, price/rating filtering, sorting, pagination-ready API, product details, comparison (up to three), wishlist, cart, checkout, and order tracking.
- AI shopping assistant with Groq-generated structured query plans when configured. Hard conditions are applied in SQL; deterministic parsing remains available when the model is unavailable.
- Floating assistant for policy questions and order tracking. Answers return source document names and versions, with a safe fallback when policy context is missing.
- Admin-only policy document ingestion for PDF, Markdown, TXT, and JSON with 700-character chunks and 100-character overlap, metadata, and Chroma indexing. The demo account is the local admin.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/categories`, `GET /api/products`, `GET /api/products/{id}`
- `GET/POST /api/cart`, `PATCH/DELETE /api/cart/{product_id}`
- `GET/POST /api/wishlist`, `POST /api/wishlist/{product_id}`
- `POST /api/orders/checkout`, `GET /api/orders`, `GET /api/orders/{id}`
- `POST /api/assistant/search`, `POST /api/assistant/chat`
- `POST /api/admin/documents`, `GET /api/admin/documents`

## Configuration

Set `GROQ_API_KEY`, `GROQ_MODEL`, and `LLM_PROVIDER=groq` in `server/.env`. The default model is `llama-3.3-70b-versatile`; use an active model ID from Groq’s [supported models](https://console.groq.com/docs/models). The `llm()` adapter in `server/app/main.py` keeps provider selection in one place. Other options include `SECRET_KEY`, `DATABASE_URL`, `CHROMA_PATH`, and `CORS_ORIGINS`. Never deploy the example secret. For production, use stronger account controls, role-based admin authorization, migrations, upload scanning, rate limits, concurrency-tested inventory updates, and a payment provider.

## Project structure

```text
client/
  src/App.jsx
  src/main.jsx
  src/styles.css
  package.json
server/
  app/main.py
  app/models.py
  app/security.py
  app/seed.py
  app/database.py
  app/config.py
  requirements.txt
  .env.example
```
