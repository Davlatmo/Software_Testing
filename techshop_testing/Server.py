"""
TechShop Flask Server
"""
import uuid
import json
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, make_response, send_from_directory
import os


app = Flask(__name__, static_folder="public")

# ---------------------------------------------------------------------------
# In-memory data 
# ---------------------------------------------------------------------------
# Our Dictionary
PRODUCTS = [
    {"id": 1, "name": "Wireless Headphones",  "price": 79.99,  "category": "electronics",  "image": "headphones.svg", "stock": 15},
    {"id": 2, "name": "Mechanical Keyboard",   "price": 129.99, "category": "electronics",  "image": "keyboard.svg",   "stock": 8},
    {"id": 3, "name": "USB-C Hub",             "price": 49.99,  "category": "electronics",  "image": "hub.svg",        "stock": 25},
    {"id": 4, "name": "Monitor Stand",         "price": 89.99,  "category": "accessories",  "image": "stand.svg",      "stock": 12},
    {"id": 5, "name": "Webcam HD",             "price": 69.99,  "category": "electronics",  "image": "webcam.svg",     "stock": 20},
    {"id": 6, "name": "Mouse Pad XL",          "price": 24.99,  "category": "accessories",  "image": "mousepad.svg",   "stock": 50},
]

# dict acting as a session store  here
SESSIONS: dict = {}

# Global users list shared across sessions 
USERS: list = [
    {"id": 1, "email": "dasha@techshop.com", "password": "dasha123", "name": "Dasha"}
]

@app.before_request
def ensure_session():
    """
    Runs before every request.
    Reads the session cookie, creates a new session if none exists.
    Stores the session data on Flask's `g` object so routes can access it.
    """
   
    session_id = request.cookies.get("sessionId")

    if not session_id or session_id not in SESSIONS:

    # Create a fresh session
        session_id = str(uuid.uuid4())          
        SESSIONS[session_id] = {
            "cart": [],
            "current_user": None,
        }

    # Attaching session data to the request context so route handlers can read it
    request.session_id = session_id
    request.session = SESSIONS[session_id]


def attach_session_cookie(response, session_id):
    """
    Helper: set the sessionId cookie on the response.
    Equivalent to: res.cookie('sessionId', sessionId, { httpOnly: true, sameSite: 'lax' })
    """
    response.set_cookie(
        "sessionId",
        session_id,
        httponly=True,     
        samesite="Lax",    
    )
    return response


@app.after_request
def set_session_cookie(response):
    """
    After every request, ensure the session cookie is present in the response.
    This mirrors Express's `res.cookie(...)` call inside `ensureSession`.
    """
    attach_session_cookie(response, request.session_id)
    return response


# ---------------------------------------------------------------------------
# CORS helper 
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    """Allow any origin with credentials — same as cors({ credentials:true, origin:true })."""
    origin = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_static(path):
    """Serve static files from the public/ folder (same as express.static)."""
    public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
    if path and os.path.exists(os.path.join(public_dir, path)):
        return send_from_directory(public_dir, path)
    # Default: serve index.html
    return send_from_directory(public_dir, "index.html")


# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------

@app.route("/api/products", methods=["GET"])
def get_products():
    """
    GET /api/products
    Optional query params: category, search, minPrice, maxPrice

    `request.args` in Flask == `req.query` in Express
    """
    category  = request.args.get("category")    # ?category=electronics
    search    = request.args.get("search")       # ?search=keyboard
    min_price = request.args.get("minPrice", type=float)  
    max_price = request.args.get("maxPrice", type=float)

    # Start with all products then filter 
    filtered = list(PRODUCTS)   # shallow copy

    if category and category != "all":
        filtered = [p for p in filtered if p["category"] == category]

    if search:
        search_lower = search.lower()
        filtered = [p for p in filtered if search_lower in p["name"].lower()]

    if min_price is not None:
        filtered = [p for p in filtered if p["price"] >= min_price]

    if max_price is not None:
        filtered = [p for p in filtered if p["price"] <= max_price]

    
    return jsonify(filtered)


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """
    GET /api/products/:id
    `<int:product_id>` is Flask's URL converter — same as req.params.id (auto-cast)
    """
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        # HTTP 404 with error body
        return jsonify({"error": "Product not found"}), 404
    return jsonify(product)


#Cart
@app.route("/api/cart", methods=["GET"])
def get_cart():
    """GET /api/cart — returns items with product details and total."""
    cart = request.session["cart"]

    # Enriching each cart item with full product info
    cart_with_products = []
    for item in cart:
        product = next((p for p in PRODUCTS if p["id"] == item["productId"]), None)
        cart_with_products.append({**item, "product": product})  # {…spread} equivalent

    total = sum(i["product"]["price"] * i["quantity"] for i in cart_with_products)
    return jsonify({"items": cart_with_products, "total": f"{total:.2f}"})


@app.route("/api/cart", methods=["POST"])
def add_to_cart():
    """POST /api/cart — body: { productId, quantity }"""
    
    data       = request.json or {}
    product_id = data.get("productId")
    quantity   = data.get("quantity", 1)

    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if product["stock"] < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    cart = request.session["cart"]
    existing = next((i for i in cart if i["productId"] == product_id), None)
    if existing:
        existing["quantity"] += quantity
    else:
        cart.append({"productId": product_id, "quantity": quantity})

    return jsonify({"message": "Added to cart", "cart": cart})


@app.route("/api/cart/<int:product_id>", methods=["PUT"])
def update_cart(product_id):
    """PUT /api/cart/:productId — body: { quantity }"""
    data     = request.json or {}
    quantity = data.get("quantity")
    cart     = request.session["cart"]

    item = next((i for i in cart if i["productId"] == product_id), None)
    if not item:
        return jsonify({"error": "Item not in cart"}), 404

    if quantity <= 0:
        request.session["cart"] = [i for i in cart if i["productId"] != product_id]
    else:
        item["quantity"] = quantity

    return jsonify({"message": "Cart updated", "cart": request.session["cart"]})


@app.route("/api/cart/<int:product_id>", methods=["DELETE"])
def remove_from_cart(product_id):
    """DELETE /api/cart/:productId"""
    request.session["cart"] = [
        i for i in request.session["cart"] if i["productId"] != product_id
    ]
    return jsonify({"message": "Removed from cart", "cart": request.session["cart"]})


@app.route("/api/cart", methods=["DELETE"])
def clear_cart():
    """DELETE /api/cart — clears the entire cart."""
    request.session["cart"] = []
    return jsonify({"message": "Cart cleared"})


#Authentication
@app.route("/api/login", methods=["POST"])
def login():
    """POST /api/login — body: { email, password }"""
    data     = request.json or {}
    email    = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = next((u for u in USERS if u["email"] == email and u["password"] == password), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    request.session["current_user"] = user
    return jsonify({
        "message": "Login successful",
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    """POST /api/logout"""
    request.session["current_user"] = None
    return jsonify({"message": "Logged out"})


@app.route("/api/register", methods=["POST"])
def register():
    """POST /api/register — body: { email, password, name }"""
    data     = request.json or {}
    email    = data.get("email")
    password = data.get("password")
    name     = data.get("name")

    if not email or not password or not name:
        return jsonify({"error": "All fields required"}), 400

    if any(u["email"] == email for u in USERS):
        return jsonify({"error": "Email already registered"}), 400

    new_user = {"id": len(USERS) + 1, "email": email, "password": password, "name": name}
    USERS.append(new_user)
    request.session["current_user"] = new_user

    return jsonify({
        "message": "Registration successful",
        "user": {"id": new_user["id"], "email": email, "name": name},
    }), 201


@app.route("/api/user", methods=["GET"])
def get_user():
    """GET /api/user — returns the currently logged-in user."""
    user = request.session.get("current_user")
    if not user:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"id": user["id"], "email": user["email"], "name": user["name"]})


#Checkout
@app.route("/api/checkout", methods=["POST"])
def checkout():
    """POST /api/checkout — body: { shipping: { address, city, zip } }"""
    cart = request.session["cart"]
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    data     = request.json or {}
    shipping = data.get("shipping", {})
    if not all(shipping.get(k) for k in ("address", "city", "zip")):
        return jsonify({"error": "Shipping information required"}), 400

    total = 0
    for item in cart:
        product = next((p for p in PRODUCTS if p["id"] == item["productId"]), None)
        total  += product["price"] * item["quantity"]
        product["stock"] -= item["quantity"]   # reduce stock (same as JS)

    order = {
        "id": int(datetime.utcnow().timestamp() * 1000),  # Date.now() equivalent
        "items": list(cart),
        "total": f"{total:.2f}",
        "shipping": shipping,
        "date": datetime.utcnow().isoformat() + "Z",
    }

    request.session["cart"] = []
    return jsonify({"message": "Order placed successfully", "order": order})


#Helath
@app.route("/api/health", methods=["GET"])
def health():
    """GET /api/health"""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"})


# Entry point
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 3000))
    print(f"TechShop server running on http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
