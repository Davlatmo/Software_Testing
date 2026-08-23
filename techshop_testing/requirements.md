# Feature Requirements: Product search and filtering

## Overview
The developer must implement a product search and filtering feature
for the TechShop e-commerce API.

## Requirements

### REQ-01: Search by name
- `GET /api/products?search=<term>` must return only products whose
  name is matcing with the search term (case insensitive)
- If no products match, return an empty array with status 200
- If the search term is empty or whitespace, return all products

### REQ-02: Filter by category
- `GET /api/products?category=<category>` must return only products
  in the specified category
- Valid categories: `electronics`, `accessories`
- If an invalid category is provided, return status 400 with
  `{ "error": "Invalid category" }`

### REQ-03: Filter by price range
- `GET /api/products?minPrice=<n>&maxPrice=<n>` must return products
  whose price is within the given range (inclusive)
- If minPrice > maxPrice, return status 400 with
  `{ "error": "minPrice cannot be greater than maxPrice" }`

### REQ-04: Combined filters
- All three filters (search, category, price) must work together
- Example: `?search=keyboard&category=electronics&maxPrice=150`
  must return electronics products with "keyboard" in the name
  that cost ≤ $150

### REQ-05: Single product endpoint
- `GET /api/products/<id>` must return a single product by ID
- If the product does not exist, return status 404 with
  `{ "error": "Product not found" }`

## Acceptance criteria
- All endpoints return JSON
- Search is case-insensitive
- All filters can be combined
- Invalid inputs return appropriate 4xx status codes