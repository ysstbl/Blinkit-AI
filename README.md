# Blinkit AI

Blinkit AI is a quick-commerce extension concept that helps customers shop for a recipe without searching for every ingredient individually: describe a dish, get its ingredients matched to grocery catalog products, review availability or substitutes, then add chosen items to a cart. Gemini handles intent and recipe extraction, while local MiniLM embeddings and PostgreSQL/pgvector connect each ingredient to catalog SKUs.

![Blinkit AI assistant interface](recipe-cart-ui/src/assets/ai-assistant.png)

## Quick-Commerce Recipe Flow

The core use case starts with a meal, not a product search. A customer can ask for the ingredients needed for a dish; the assistant extracts ingredient names and quantities, normalizes them to familiar grocery terms, and searches the catalog for relevant SKUs. Each match includes pack size, price, and availability. When the closest match is unavailable, the assistant can suggest an in-stock alternative. The customer reviews the checklist, changes selections, and adds only the chosen items to the cart.

This reduces the work of translating a recipe into a basket: shoppers do not have to leave the cooking intent, search item by item, compare pack options, and manually rebuild a list. Direct product availability and price questions are supported too, but recipe-to-cart is the primary workflow.

The repository demonstrates an integration pattern for a quick-commerce experience, not a production plugin for a specific commerce platform. The AI assistant has its own API and catalog; the Blinkit-style storefront routes currently use separate static sample products and an in-memory cart.

## Architecture & System Design

```mermaid
flowchart LR
	 Shopper --> UI[React 19 + Vite]
	 UI -->|POST /api/blinkit-assistant| API[FastAPI]
	 API -->|Structured intent and recipe extraction| Gemini[Google Gemini]
	 API -->|384-dimensional query vector| Model[all-MiniLM-L6-v2]
	 Model --> API
	 API -->|Cosine-distance candidate search| DB[(PostgreSQL + pgvector)]
	 DB -->|Top 100 candidates| Rank[Lexical relevance reranker]
	 Rank --> API
	 API -->|chat or staged checklist| UI
	 UI -->|User confirms selected items| Cart[In-memory assistant cart]
	 UI -->|/blinkit and /cart| Storefront[Static replica products]
```

The assistant separates language understanding from catalog retrieval. For a recipe request, Gemini emits schema-constrained JSON containing the dish and ingredient names, quantities, and pantry-staple flags. The backend normalizes ingredient terminology, encodes each ingredient with `all-MiniLM-L6-v2`, asks pgvector for the 100 nearest catalog rows, then reranks those candidates using token overlap, exact phrase matches, category signals, and penalties for likely processed-product drift. The selected SKU, pack size, price, stock state, and any alternative are returned for customer review. Direct product requests follow the same retrieval path; catalog price questions use SQL filtering and ordering.

The Vite development server proxies `/api` to FastAPI on port `8000`. The `/blinkit` and `/cart` routes instead use a hard-coded product list and browser-memory cart. They are deliberately separate from the database-backed AI flow today.

## Technical Feats & Benchmark Status

- Uses a local 384-dimensional `all-MiniLM-L6-v2` model for query and catalog embeddings, while reserving Gemini for language interpretation rather than embedding every query remotely.
- Combines vector candidate generation with a domain-specific lexical reranker to mitigate semantically close but operationally wrong matches (for example, a processed product returned for a raw ingredient request).
- Models ingredient-to-SKU matches, availability, and substitution details in typed backend response objects; the frontend tracks checklist selection and only adds confirmed items to its cart.
- Supports price extrema queries with SQL filtering and ordering over in-stock catalog entries.
- No latency, throughput, or relevance benchmark is currently recorded in the repository. The current retrieval query orders by vector distance without creating an ANN index, so performance should be measured before making scale claims.

## Developer Experience (Quick Start)

Prerequisites: Python 3.10+, Node.js 20.19+ or 22.12+, a PostgreSQL database with pgvector, and a Gemini API key.

1. **Create the catalog table** in a fresh development database:

	```sql
	CREATE EXTENSION IF NOT EXISTS vector;

	CREATE TABLE grocery_catalog (
		 sku_id VARCHAR(50) PRIMARY KEY,
		 name VARCHAR(255) NOT NULL,
		 category VARCHAR(100),
		 pack_size VARCHAR(50),
		 price NUMERIC(10, 2),
		 in_stock BOOLEAN,
		 stock_qty INTEGER,
		 dark_store_id VARCHAR(50),
		 embedding VECTOR(384)
	);
	```

2. **Configure and start the API.** Create `backend/.env` with your own credentials, then run the commands below from the repository root. The seeder downloads the BigBasket dataset through `kagglehub`, generates local embeddings, and replaces table contents; use only a disposable development database.

	```dotenv
	DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
	GEMINI_API_KEY=your-gemini-api-key
	```

	```bash
	cd backend
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	python seed_catalog.py
	python -m uvicorn main:app --reload --port 8000
	```

3. **Start the UI** in a second terminal:

	```bash
	cd recipe-cart-ui
	npm install
	npm run dev
	```

	Open the Vite URL (normally `http://localhost:5173`). The assistant is at `/`, and the static storefront is at `/blinkit`.

	## Deploying to Render

	The repository includes `render.yaml` for deploying the FastAPI backend and React static site as two Render services. In Render, create a Blueprint from this repository, then set the `DATABASE_URL` and `GEMINI_API_KEY` secrets for `blinkit-ai-api`. Replace the placeholder `ALLOWED_ORIGINS` value with the final frontend URL, and set `VITE_API_URL` on `blinkit-ai-ui` to the public API URL. `VITE_API_URL` is embedded during the frontend build, so redeploy the UI after changing it.

	The database must have the `vector` extension and the `grocery_catalog` table before the API can answer requests. Run the catalog setup/seeding steps against the production database only after reviewing them; the seeder replaces existing catalog rows.

## API Contract

`POST /api/blinkit-assistant` accepts `{"prompt":"Is paneer available?"}`. Responses use `type: "chat"` with a `message`, or `type: "checklist"` with a `message` and product/ingredient `data`. The Vite proxy is development-only; deploy the frontend and API behind an explicitly configured production origin and route.

## Scalability Roadmap

- **Catalog scale:** add and benchmark a pgvector HNSW or IVFFlat index, inspect query plans, and batch/version embedding generation as catalog updates grow.
- **Request volume:** pool database connections, isolate or serve the eagerly loaded embedding model independently, and scale stateless API workers only after measuring model memory and concurrent inference behavior.
- **Inventory correctness:** replace randomized seed availability and browser-memory carts with authoritative inventory, persistent carts, and transactional/idempotent reservation flows; add load and relevance tests before setting SLOs.

## Operational Notes

> [!WARNING]
> `backend/initialize_catalog.py` contains a hard-coded database connection URL instead of reading `DATABASE_URL`. Do not run it; if that credential is active, rotate it and move connection settings to environment variables. The quick start uses `seed_catalog.py`, which also truncates `grocery_catalog` before loading data.

- The full seed assigns availability randomly; it is sample data, not live inventory.
- The backend loads the sentence-transformers model at process startup. The initial run downloads model files, and each API process keeps the model in memory.
- CORS is controlled by the comma-separated `ALLOWED_ORIGINS` environment variable.

## Repository Map

```text
backend/
  main.py                 FastAPI app setup, middleware, and route registration
  app/
    api/routes/           HTTP endpoints for the assistant and health check
    clients/               Gemini, Hugging Face, and PostgreSQL integrations
    core/config.py         Environment-backed application settings
    models/                API and LLM data schemas
    repositories/          Catalog SQL queries
    services/              Intent, catalog, recipe, checklist, and assistant logic
  seed_catalog.py         BigBasket ingestion and local embedding generation
  initialize_catalog.py   Small sample initializer (unsafe as committed; see warning)
recipe-cart-ui/
  src/App.jsx             Assistant chat, checklist review, and in-memory cart
  blinkit-replica/        Static storefront, local search, categories, and cart UI
```

## Development Commands

Run from `recipe-cart-ui`:

```bash
npm run dev       # Vite development server
npm run build     # Production bundle
npm run lint      # ESLint
npm run preview   # Serve the production bundle locally
```
