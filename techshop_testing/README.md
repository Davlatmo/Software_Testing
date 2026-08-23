# TechShop — Project Documentation

## What is TechShop?
TechShop is a demo e-commerce REST API built with Python and Flask.
It simulates a real online store with products, a shopping cart,
user authentication, and checkout.

## Project structure
```
TechShop/
├── Server.py                    ← Flask application (the backend)
├── agent_coordinator.py         ← Agentic testing pipeline entry point
├── agents.py                    ← Phase agents (1, 2, 3, 4)
├── base_agent.py                ← Shared agent logic
├── tools.py                     ← Tools agents can call
├── requirements.md              ← Feature requirements (input to pipeline)
├── public/                      ← Frontend HTML/CSS/JS
│   ├── index.html
│   ├── cart.html
│   ├── checkout.html
│   ├── login.html
│   ├── register.html
│   ├── styles.css
│   ├── app.js
│   └── images/
├── tests/
│   ├── test_api.py              ← Existing API tests (style reference)
│   ├── browser_tests.py         ← Existing browser tests
│   ├── agentic_tests.py         ← Existing agentic tests
│   └── unit_test_template.py    ← Template for generated tests
└── reports/                     ← Pipeline reports (auto-generated)
```

## The API

### Base URL
`http://localhost:3000`

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products` | Get all products. Supports `?search=`, `?category=`, `?minPrice=`, `?maxPrice=` |
| GET | `/api/products/<id>` | Get a single product by ID |

**Product object:**
```json
{
  "id": 1,
  "name": "Wireless Headphones",
  "price": 79.99,
  "category": "electronics",
  "image": "headphones.svg",
  "stock": 15
}
```

**Categories:** `electronics`, `accessories`

### Cart

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| GET | `/api/cart` | — | Get current cart with totals |
| POST | `/api/cart` | `{ productId, quantity }` | Add item to cart |
| PUT | `/api/cart/<productId>` | `{ quantity }` | Update item quantity |
| DELETE | `/api/cart/<productId>` | — | Remove one item |
| DELETE | `/api/cart` | — | Clear entire cart |

**Cart response:**
```json
{
  "items": [
    { "productId": 1, "quantity": 2, "product": { ... } }
  ],
  "total": "159.98"
}
```

### Authentication

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/login` | `{ email, password }` | Login |
| POST | `/api/logout` | — | Logout |
| POST | `/api/register` | `{ name, email, password }` | Register new user |
| GET | `/api/user` | — | Get current logged-in user |

**Demo account:** `dasha@techshop.com` / `dasha123`

### Checkout

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/checkout` | `{ shipping: { address, city, zip } }` | Place order |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Returns `{ status: "healthy", timestamp: "..." }` |

## Sessions
The API uses cookie-based sessions. Each client gets a `sessionId`
cookie on first request. Cart and login state are stored per session
in memory (the session resets when our server restarts).

## Error responses
All errors follow this format:
```json
{ "error": "Human-readable error message" }
```

Common status codes:
- `200` — success
- `201` — created (registration)
- `400` — bad request (missing or invalid input)
- `401` — unauthorized (wrong credentials, not logged in)
- `404` — not found
- `500` — server error

## Running the server
```coomand line
python Server.py
# Server starts on http://localhost:3003
```

## Running tests
```command line
# API tests
python tests/test_api.py

# Browser tests
python tests/browser_tests.py

# Agentic tests
python tests/agentic_tests.py

# Full agentic pipeline (after a git commit)
python agent_coordinator.py --requirements requirements.md
```

## Domain glossary
- **Product** — an item in the store with name, price, category, stock count
- **Cart** —  list of products with quantities
- **Session** — browser session identified by a cookie, holds cart and user state
- **Stock** — number of units available; decremented when checkout succeeds
- **Checkout** — converts cart into an order, reduces stock, makes empty the cart
- **Order** — result of a successful checkout: items, total price, shipping address, date 