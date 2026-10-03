# Blinkit AI

> AI recipe-to-cart assistant that converts natural-language meal requests into verified grocery checklists using structured Gemini extraction, vector search, lexical reranking, and out-of-stock substitution.

![Blinkit AI assistant interface](recipe-cart-ui/src/assets/ai-assistant.png)

## Why this project

Most grocery search starts with a product. Blinkit AI starts with the shopper's intent:

> “I want to make paneer tikka for four people.”

The assistant extracts the ingredients, normalizes grocery terminology, matches each ingredient to catalog SKUs, handles unavailable products, and lets the shopper confirm the final checklist before adding items to a cart.

This project demonstrates an end-to-end AI retrieval workflow rather than a chatbot connected directly to a database:

- Gemini performs structured intent classification and recipe extraction.
- Hugging Face `all-MiniLM-L6-v2` creates query embeddings.
- PostgreSQL with pgvector retrieves semantic candidates.
- A domain-specific lexical reranker reduces incorrect matches such as processed products returned for raw ingredients.
- Typed responses preserve price, pack size, availability, and substitution context.
- The UI requires user confirmation before products reach the cart.

## Product flow

```text
“What do I need to make paneer tikka?”
                    ↓
        Structured recipe extraction
                    ↓
       Grocery-term normalization
                    ↓
       Embedding-based catalog search
                    ↓
          Lexical relevance reranking
                    ↓
        Stock-aware substitution choice
                    ↓
       Reviewable checklist in the UI
                    ↓
             User confirms cart
```

The assistant also supports:

- Specific product and availability requests
- Cheapest and most expensive catalog queries
- General grocery-related conversation
- Out-of-stock alternatives

## Application data flow

Every assistant request moves through the same high-level pipeline:

```text
Prompt
  → Intent classification
  → Service selection
  → External model/database calls
  → Typed response
  → Checklist review
  → Cart confirmation
```

In the implementation, that pipeline maps to:

1. **Prompt** — The React UI sends `{ "prompt": "..." }` to `POST /api/blinkit-assistant`.
2. **Intent classification** — `intent_service.py` asks Gemini to classify the request as chat, inventory, recipe extraction, or catalog query.
3. **Service selection** — `assistant_service.py` dispatches to the appropriate catalog, checklist, recipe, or chat path.
4. **External model/database calls** — The selected service uses Gemini, Hugging Face embeddings, and/or PostgreSQL with pgvector.
5. **Typed response** — Pydantic-backed structures return either a chat message or a checklist containing matched SKUs, prices, pack sizes, stock state, and substitutions.
6. **Checklist review** — The frontend displays the proposed items and lets the user select or unselect them.
7. **Cart confirmation** — Only the user's selected items are converted into cart products and added to the browser-memory cart.

## Demo

Run the project locally using the setup below, then try:

- `Give me everything I need to make paneer tikka`
- `Find olive oil and add it to my list`
- `What is the cheapest dairy item?`
- `Is paneer available?`

The assistant UI is available at `/assistant`. The static storefront is available at `/blinkit`, and the browser-memory cart is available at `/cart`.

For a portfolio deployment, the next presentation step is to publish the two services described in [render.yaml](render.yaml), add a short walkthrough video, and place the live demo URL here.

## Architecture

```mermaid
flowchart LR
    Shopper --> UI[React 19 + Vite]
    UI -->|POST /api/blinkit-assistant| Route[FastAPI route]
    Route --> Assistant[Assistant service]
    Assistant --> Intent[Intent service]
    Intent --> Gemini[Gemini client]
    Assistant --> Recipe[Recipe service]
    Assistant --> Checklist[Checklist service]
    Recipe --> Catalog[Catalog service]
    Checklist --> Catalog
    Catalog --> Embeddings[Hugging Face embeddings]
    Catalog --> Repository[Catalog repository]
    Repository --> DB[(PostgreSQL + pgvector)]
    DB --> Rerank[Lexical relevance reranker]
    Rerank --> UI
    UI --> Cart[Browser-memory cart]
```

### Code boundaries

```text
backend/main.py
  FastAPI application setup, CORS, and route registration

backend/app/api/routes/
  HTTP adapters for assistant and health endpoints

backend/app/services/
  Intent routing, recipe extraction, catalog matching,
  checklist creation, and request orchestration

backend/app/clients/
  Gemini, Hugging Face, and PostgreSQL integrations

backend/app/repositories/
  SQL queries for catalog retrieval and price queries

backend/app/models/
  Pydantic API models and Gemini response schemas
```

The route layer remains intentionally thin. Services contain business behavior, repositories contain SQL, and clients contain external-system integration.

## Retrieval and matching design

The catalog search pipeline:

1. Prefixes the user query with `Product:`.
2. Generates a query vector with `all-MiniLM-L6-v2`.
3. Retrieves the top 100 candidates using pgvector distance.
4. Optionally filters obvious non-food candidates for recipe requests.
5. Reranks candidates using:
   - Token overlap
   - Exact phrase matches
   - Food-category signals
   - Fresh-product boosts
   - Processed-product boosts when explicitly requested
   - Processed-product penalties when a raw ingredient is requested
   - Name-length penalties for noisy matches
6. Returns the top 15 typed `MatchedSKU` results.

This layered approach is deliberate: vector search provides recall, while lexical and domain rules improve precision.

## Reliability decisions

The assistant is designed to fail explicitly instead of presenting uncertain results as successful actions:

- A product is not considered added merely because it was found.
- The UI requires the shopper to review and confirm checklist items.
- Out-of-stock products retain their original match and substitution reason.
- If every candidate is unavailable, the response says so.
- If no catalog match exists, the assistant does not create a fake product.
- Malformed Gemini JSON produces an explicit server error.
- General chat responses are instructed not to claim catalog searches or cart changes.

These boundaries keep language-model output separate from inventory and cart decisions.

## Engineering decisions

### Why Gemini is not used for catalog retrieval

Gemini is used for language understanding: intent classification, ingredient extraction, and normalization. Product selection comes from the catalog and its embeddings, so results can include concrete SKU, price, pack size, and availability data.

### Why vector search is combined with lexical reranking

Embeddings can identify semantically related products but may confuse raw ingredients with pastes, powders, sauces, or non-food products. The reranker adds grocery-specific constraints that are easy to inspect and test.

### Why stock selection is separate from product matching

The closest semantic match may be unavailable. Matching and availability are therefore represented separately so the system can preserve the original product, find an alternative, and explain the choice.

### Why the cart requires confirmation

Recipe extraction and product matching are recommendations, not purchases. The staged checklist gives the user control over substitutions and pantry staples.

## Data and database setup

Prerequisites:

- Python 3.10+
- Node.js 20.19+ or 22.12+
- PostgreSQL with the pgvector extension
- Gemini API key
- Hugging Face token for runtime embeddings

Create the catalog table in a disposable development database:

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

Create `backend/.env` with your own credentials:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
GEMINI_API_KEY=your-gemini-api-key
HF_TOKEN=your-hugging-face-token
HF_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ALLOWED_ORIGINS=http://localhost:5173
```

The seeder downloads the BigBasket dataset through `kagglehub`, generates local MiniLM embeddings, assigns sample availability, and replaces the contents of `grocery_catalog`. Use only a disposable development database.

## Run locally

Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed_catalog.py
python -m uvicorn main:app --reload --port 8000
```

Start the frontend in a second terminal:

```bash
cd recipe-cart-ui
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`.

## API contract

### `POST /api/blinkit-assistant`

Request:

```json
{
  "prompt": "Is paneer available?"
}
```

Chat response:

```json
{
  "type": "chat",
  "message": "..."
}
```

Checklist response:

```json
{
  "type": "checklist",
  "message": "...",
  "data": [
    {
      "canonical_name": "paneer",
      "quantity": "200 g",
      "is_pantry_staple": false,
      "selected_sku": {},
      "is_substituted": false,
      "raw_matches": []
    }
  ]
}
```

## Caching strategy

The catalog is fixed for this portfolio project, so catalog-derived computations are good candidates for long-lived, versioned caching if caching is added:

| Data | Suggested TTL |
| --- | ---: |
| Product embeddings | 1 year or no expiry |
| Catalog search results | 1 year or no expiry |
| Cheapest/most expensive queries | 1 year or no expiry |
| Recipe ingredient extraction | 1 year with prompt/model versioning |
| General chat responses | Do not cache by default |

Use versioned keys such as:

```text
embedding:v1:all-MiniLM-L6-v2:paneer
catalog-search:v1:paneer
recipe:v1:butter-chicken
```

If the catalog, model, prompt, or reranking rules change, increment the version. An in-memory TTL cache is sufficient for a single-process portfolio demo; Redis becomes useful when multiple backend workers need a shared cache.

## Evaluation plan

No relevance benchmark is currently committed. The next meaningful evaluation should use a small labeled query set covering:

- Raw versus processed ingredients
- Fresh versus packaged products
- Food versus non-food ambiguity
- Exact product names
- Product and category price queries
- Out-of-stock substitutions

Compare vector-only retrieval with vector retrieval plus lexical reranking using:

- Top-1 accuracy
- Top-5 recall
- Processed-product false-match rate
- Non-food false-match rate
- Successful substitution rate

Only publish measured results. The retrieval query currently orders by vector distance without an ANN index, so performance claims should be validated with query plans and representative catalog sizes.

## Validation commands

Backend:

```bash
python -m compileall -q backend
python -c "import sys; sys.path.insert(0, 'backend'); import main; print(main.app.title)"
```

Frontend:

```bash
cd recipe-cart-ui
npm run lint
npm run build
```

## Deployment

[render.yaml](render.yaml) defines separate Render services for the backend and frontend. Configure:

- `DATABASE_URL`
- `GEMINI_API_KEY`
- `HF_TOKEN`
- `ALLOWED_ORIGINS`
- `VITE_API_URL`

The database must already contain the pgvector extension and `grocery_catalog` table. Review the seeding process before using it against any persistent database because it truncates the catalog.

## Known limitations and roadmap

> [!WARNING]
> `backend/initialize_catalog.py` contains a hard-coded database connection URL. Do not run it. If that credential is active, rotate it and move the connection settings to environment variables.

Current limitations:

- The seeded catalog uses randomized sample availability, not live inventory.
- The assistant cart is held in browser memory.
- There is no persistent user account, checkout, or inventory reservation flow.
- The current retrieval query has no ANN index.
- There are no committed automated relevance benchmarks yet.
- The runtime still uses the legacy `google-generativeai` package and should migrate to Google's current SDK.

Next improvements:

1. Add a deterministic demo mode so the UI remains demonstrable without external API availability.
2. Add labeled retrieval and substitution tests.
3. Add versioned caching for fixed catalog-derived data.
4. Benchmark and add an HNSW or IVFFlat pgvector index.
5. Add connection pooling and persistent carts.
6. Record a short walkthrough showing recipe extraction, matching, substitution, and confirmation.

## Repository map

```text
backend/
├── main.py
├── app/
│   ├── api/routes/
│   │   ├── assistant.py
│   │   └── health.py
│   ├── clients/
│   │   ├── embeddings_client.py
│   │   ├── gemini_client.py
│   │   └── postgres_client.py
│   ├── core/config.py
│   ├── models/schemas.py
│   ├── repositories/catalog_repository.py
│   └── services/
│       ├── assistant_service.py
│       ├── catalog_service.py
│       ├── checklist_service.py
│       ├── intent_service.py
│       └── recipe_service.py
├── seed_catalog.py
└── initialize_catalog.py

recipe-cart-ui/
├── src/App.jsx
└── blinkit-replica/
    └── App.jsx
```
