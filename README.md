# Blinkit AI

An AI-powered grocery assistant that turns recipe requests and product questions into a reviewable shopping checklist. It combines Gemini for intent and recipe understanding with a PostgreSQL + pgvector catalog and a React/Vite shopping interface.

![Blinkit AI assistant interface](recipe-cart-ui/src/assets/hero.png)

## What it does

- Understands recipe requests such as “Paneer butter masala for two” and extracts the required ingredients.
- Searches a grocery catalog with local `all-MiniLM-L6-v2` embeddings plus lexical re-ranking.
- Checks availability and suggests an in-stock substitute when the closest match is unavailable.
- Answers catalog questions such as the cheapest or most expensive in-stock item, optionally filtered by product terms.
- Keeps results staged for review so shoppers can select items before adding them to the cart.
- Includes a static Blinkit-inspired storefront at `/blinkit` for browsing the replica experience.

## Architecture

```mermaid
flowchart LR
		UI[React + Vite client] -->|POST /api/blinkit-assistant| API[FastAPI assistant]
		API --> LLM[Google Gemini]
		API --> EMB[Local MiniLM embeddings]
		API --> DB[(PostgreSQL + pgvector)]
		API --> UI
```

The Vite development server proxies `/api` requests to the FastAPI server on port `8000`.

## Project structure

```text
.
├── backend/
│   ├── main.py                 # FastAPI application and assistant router
│   ├── initialize_catalog.py   # Small sample catalog/schema initializer
│   └── seed_catalog.py         # Full catalog ingestion from Kaggle
└── recipe-cart-ui/
		├── src/App.jsx             # Assistant chat and checklist/cart workflow
		└── blinkit-replica/        # Static storefront route
```

## Prerequisites

- Python 3.10+ and Node.js 18+
- A PostgreSQL database with the `pgvector` extension available
- A Google Gemini API key
- Enough local disk and memory for the sentence-transformers model on first startup

## Getting started

### 1. Configure the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
GEMINI_API_KEY=your-gemini-api-key
```

The application expects a `grocery_catalog` table with a 384-dimensional `embedding` column. The sample initializer creates this schema and inserts a small catalog. The full seeder downloads the BigBasket dataset through `kagglehub` and replaces the catalog with generated embeddings.

```bash
# Use the small sample catalog during development.
python initialize_catalog.py

# Or, after configuring the database and Kaggle access, load the larger dataset.
python seed_catalog.py
```

Start the API from the `backend` directory:

```bash
python -m uvicorn main:app --reload --port 8000
```

### 2. Start the frontend

In a second terminal:

```bash
cd recipe-cart-ui
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`. The assistant is available at `/`; the storefront replica is available at `/blinkit`.

## API

### `POST /api/blinkit-assistant`

Request:

```json
{
	"prompt": "Is paneer available?"
}
```

The response has one of these shapes:

| `type` | Purpose |
| --- | --- |
| `chat` | Natural-language response or catalog price answer in `message` |
| `checklist` | Reviewable product or recipe results in `data`, plus a message |

The frontend sends checklist items to the local cart only after the shopper selects them.

## Development commands

Run these from `recipe-cart-ui`:

```bash
npm run dev       # Start Vite with hot reload
npm run build     # Create a production build
npm run lint      # Run ESLint
npm run preview   # Preview the production build
```


> [!WARNING]
> Keep database credentials and API keys in environment variables. Review the connection handling in [`backend/initialize_catalog.py`](backend/initialize_catalog.py) before using it in a shared or production environment; the file currently contains a connection string in source rather than reading `DATABASE_URL`.

## Limitations

- The cart is held in browser memory and is not persisted.
- The `/blinkit` storefront uses static sample products and controls; it is a visual replica, not a connected checkout flow.
- Catalog search and recipe extraction depend on a reachable PostgreSQL database, a populated catalog, Gemini, and the local embedding model.
