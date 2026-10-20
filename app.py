#!/usr/bin/env python3
"""
Grocery - Modern Cross-Platform Shopping App
=============================================
Works on Windows, macOS, Linux, and Android (via browser).
Ready for public hosting with Gunicorn/Waitress.

Admin: groceradmin / 12345Grocer
"""

import os
import secrets
import sqlite3
import time
from datetime import datetime
from functools import wraps

import bcrypt
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, g, jsonify
)

# Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
DATABASE = os.path.join(INSTANCE_DIR, 'grocery.db')

app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FORCE_HTTPS') == '1'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days

# Admin credentials
ADMIN_USER = os.environ.get('ADMIN_USERNAME', 'groceradmin')
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', '12345Grocer')

# Rate limiting
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
_failed_attempts = {}

# Database helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
    return db

@app.teardown_appcontext
def close_db(exception=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Products
PRODUCTS = [
    ("Fresh Apples", "🍎", "Fruits", 2.99, "Crispy red apples"),
    ("Bananas", "🍌", "Fruits", 1.49, "Sweet ripe bananas"),
    ("Oranges", "🍊", "Fruits", 3.49, "Juicy oranges"),
    ("Grapes", "🍇", "Fruits", 4.29, "Seedless grapes"),
    ("Strawberries", "🍓", "Fruits", 5.99, "Fresh strawberries"),
    ("Whole Milk", "🥛", "Dairy", 3.29, "1 gallon whole milk"),
    ("Cheddar Cheese", "🧀", "Dairy", 4.99, "Sharp cheddar block"),
    ("Eggs (Dozen)", "🥚", "Dairy", 3.99, "Farm fresh eggs"),
    ("Yogurt", "🥣", "Dairy", 1.29, "Greek yogurt cup"),
    ("White Bread", "🍞", "Bakery", 2.49, "Fresh baked bread"),
    ("Croissants", "🥐", "Bakery", 3.99, "Buttery croissants"),
    ("Bagels", "🥯", "Bakery", 3.49, "Everything bagels"),
    ("Broccoli", "🥦", "Vegetables", 1.99, "Fresh broccoli florets"),
    ("Carrots", "🥕", "Vegetables", 1.29, "Crunchy carrots"),
    ("Tomatoes", "🍅", "Vegetables", 2.19, "Vine ripe tomatoes"),
    ("Potatoes", "🥔", "Vegetables", 2.79, "Russet potatoes"),
    ("Onions", "🧅", "Vegetables", 1.69, "Yellow onions"),
    ("Chicken Breast", "🍗", "Meat", 6.99, "Boneless skinless"),
    ("Ground Beef", "🥩", "Meat", 7.49, "80/20 ground beef"),
    ("Salmon Fillet", "🐟", "Meat", 9.99, "Atlantic salmon"),
    ("Rice", "🍚", "Pantry", 4.49, "Long grain rice"),
    ("Pasta", "🍝", "Pantry", 1.99, "Spaghetti pasta"),
    ("Olive Oil", "🫒", "Pantry", 8.99, "Extra virgin olive oil"),
    ("Coffee", "☕", "Beverages", 7.99, "Premium ground coffee"),
    ("Orange Juice", "🧃", "Beverages", 4.49, "100% orange juice"),
    ("Ice Cream", "🍦", "Frozen", 5.99, "Vanilla ice cream"),
    ("Frozen Pizza", "🍕", "Frozen", 6.49, "Pepperoni pizza"),
    ("Paper Towels", "🧻", "Household", 5.49, "Absorbent paper towels"),
    ("Dish Soap", "🧽", "Household", 2.99, "Lemon scented dish soap"),
]

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)
        # Seed products
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executemany("INSERT INTO products (name, emoji, category, price, description) VALUES (?,?,?,?,?)", PRODUCTS)
        # Seed admin
        admin = conn.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USER,)).fetchone()
        if not admin:
            conn.execute("INSERT INTO users (username, email, password_hash, is_admin, created_at) VALUES (?,?,?,?,datetime('now'))",
                        (ADMIN_USER, "admin@grocery.app", hash_password(ADMIN_PASS), 1))

# Password helpers
def hash_password(plain):
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except:
        return False

def password_strong(pw):
    if len(pw) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.islower() for c in pw):
        return False, "Need a lowercase letter"
    if not any(c.isupper() for c in pw):
        return False, "Need an uppercase letter"
    if not any(c.isdigit() for c in pw):
        return False, "Need a digit"
    return True, ""

# Auth
def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue", "warning")
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Admin login required", "warning")
            return redirect(url_for('login', next=request.path))
        if not user['is_admin']:
            flash("Access denied - Admin only", "error")
            return redirect(url_for('shop'))
        return f(*args, **kwargs)
    return decorated

def csrf_token():
    token = session.get('_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf'] = token
    return token

def check_csrf():
    sent = request.form.get('_csrf_token')
    if not sent or sent != session.get('_csrf'):
        abort(400)

def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart
    session.modified = True

def cart_count():
    cart = get_cart()
    return sum(cart.values())

def cart_total():
    cart = get_cart()
    if not cart:
        return 0.0, []
    db = get_db()
    items = []
    total = 0.0
    for pid, qty in cart.items():
        p = db.execute("SELECT * FROM products WHERE id = ?", (int(pid),)).fetchone()
        if p:
            line = p['price'] * qty
            total += line
            items.append({'product': p, 'qty': qty, 'line_total': round(line, 2)})
    return round(total, 2), items

# Rate limiting
def lock_key(username):
    return f"{request.remote_addr}:{username.lower()}"

def is_locked(username):
    rec = _failed_attempts.get(lock_key(username))
    if not rec:
        return 0
    if time.time() - rec['last'] > LOCKOUT_SECONDS:
        _failed_attempts.pop(lock_key(username), None)
        return 0
    if rec['count'] >= MAX_ATTEMPTS:
        return int(LOCKOUT_SECONDS - (time.time() - rec['last']))
    return 0

def record_fail(username):
    k = lock_key(username)
    rec = _failed_attempts.setdefault(k, {'count': 0, 'last': 0})
    rec['count'] += 1
    rec['last'] = time.time()

@app.context_processor
def inject():
    return {'current_user': current_user(), 'csrf_token': csrf_token, 'cart_count': cart_count()}

# Routes
@app.route('/')
def index():
    if current_user():
        return redirect(url_for('shop'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('shop'))
    if request.method == 'POST':
        check_csrf()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        time.sleep(0.1)
        wait = is_locked(username)
        if wait:
            flash(f"Too many attempts. Try again in {wait}s", "error")
            return render_template('login.html')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        hashed = user['password_hash'] if user else hash_password('dummy')
        if user and verify_password(password, hashed):
            _failed_attempts.pop(lock_key(username), None)
            session.clear()
            session['user_id'] = user['id']
            session.permanent = True
            flash(f"Welcome back, {user['username']}!", "success")
            nxt = request.args.get('next') or url_for('shop')
            return redirect(nxt if nxt.startswith('/') else url_for('shop'))
        else:
            record_fail(username)
            flash("Invalid username or password", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user():
        return redirect(url_for('shop'))
    if request.method == 'POST':
        check_csrf()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not all([username, email, password, confirm]):
            flash("All fields required", "error")
        elif password != confirm:
            flash("Passwords don't match", "error")
        else:
            ok, msg = password_strong(password)
            if not ok:
                flash(msg, "error")
            else:
                db = get_db()
                if db.execute("SELECT 1 FROM users WHERE username=? OR email=?", (username, email)).fetchone():
                    flash("Username or email already exists", "error")
                else:
                    db.execute("INSERT INTO users (username,email,password_hash,is_admin,created_at) VALUES (?,?,?,?,datetime('now'))",
                              (username, email, hash_password(password), 0))
                    db.commit()
                    flash("Account created! Please log in", "success")
                    return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout', methods=['POST'])
def logout():
    check_csrf()
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

@app.route('/shop')
@login_required
def shop():
    db = get_db()
    cat = request.args.get('category', 'All')
    cats = ['All'] + [r['category'] for r in db.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()]
    if cat == 'All':
        products = db.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    else:
        products = db.execute("SELECT * FROM products WHERE category=? ORDER BY name", (cat,)).fetchall()
    return render_template('shop.html', products=products, categories=cats, active=cat)

@app.route('/cart')
@login_required
def cart():
    total, items = cart_total()
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add/<int:pid>', methods=['POST'])
@login_required
def add_to_cart(pid):
    check_csrf()
    db = get_db()
    if not db.execute("SELECT 1 FROM products WHERE id=?", (pid,)).fetchone():
        abort(404)
    cart = get_cart()
    cart[str(pid)] = cart.get(str(pid), 0) + 1
    save_cart(cart)
    flash("Item added to cart", "success")
    return redirect(request.referrer or url_for('shop'))

@app.route('/cart/update', methods=['POST'])
@login_required
def update_cart():
    check_csrf()
    pid = request.form.get('pid')
    action = request.form.get('action')
    cart = get_cart()
    if pid in cart:
        if action == 'inc':
            cart[pid] += 1
        elif action == 'dec':
            cart[pid] -= 1
            if cart[pid] <= 0:
                del cart[pid]
        elif action == 'remove':
            del cart[pid]
        save_cart(cart)
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    check_csrf()
    total, items = cart_total()
    if not items:
        flash("Your cart is empty", "warning")
        return redirect(url_for('shop'))
    db = get_db()
    cur = db.execute("INSERT INTO orders (user_id, total, created_at) VALUES (?,?,datetime('now'))",
                     (session['user_id'], total))
    oid = cur.lastrowid
    for it in items:
        db.execute("INSERT INTO order_items (order_id, product_id, qty, price) VALUES (?,?,?,?)",
                   (oid, it['product']['id'], it['qty'], it['product']['price']))
    db.commit()
    save_cart({})
    flash(f"Order placed successfully! Total: ${total:.2f}", "success")
    return redirect(url_for('history'))

@app.route('/history')
@login_required
def history():
    db = get_db()
    orders = db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (session['user_id'],)).fetchall()
    result = []
    for o in orders:
        items = db.execute("""SELECT p.name, p.emoji, oi.qty, oi.price, (oi.qty*oi.price) as subtotal
                            FROM order_items oi JOIN products p ON p.id=oi.product_id
                            WHERE oi.order_id=?""", (o['id'],)).fetchall()
        result.append({'order': o, 'items': items})
    return render_template('history.html', orders=result)

@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    users = db.execute("""SELECT u.*, 
                        (SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) as order_count,
                        (SELECT COALESCE(SUM(total),0) FROM orders o WHERE o.user_id=u.id) as spent
                        FROM users u ORDER BY u.id""").fetchall()
    bought = db.execute("""SELECT u.username, p.name, p.emoji, oi.qty, oi.price, 
                          (oi.qty*oi.price) as subtotal, o.id as order_id, o.created_at
                          FROM order_items oi
                          JOIN orders o ON o.id=oi.order_id
                          JOIN users u ON u.id=o.user_id
                          JOIN products p ON p.id=oi.product_id
                          ORDER BY o.id DESC""").fetchall()
    best = db.execute("""SELECT p.name, p.emoji, SUM(oi.qty) as sold, SUM(oi.qty*oi.price) as revenue
                        FROM order_items oi JOIN products p ON p.id=oi.product_id
                        GROUP BY p.id ORDER BY sold DESC LIMIT 10""").fetchall()
    stats = db.execute("SELECT (SELECT COUNT(*) FROM users) as users, (SELECT COUNT(*) FROM orders) as orders, (SELECT COALESCE(SUM(total),0) FROM orders) as revenue").fetchone()
    return render_template('admin.html', users=users, bought=bought, bestsellers=best, stats=stats)

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    print(f"🌿 Grocery running on http://{host}:{port}")
    print(f"👨‍💼 Admin: {ADMIN_USER} / {ADMIN_PASS}")
    app.run(host=host, port=port, debug=os.environ.get('DEBUG') == '1')
