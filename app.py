import os, sqlite3, json, uuid, secrets, re, time, gzip, requests
from datetime import datetime, timedelta
from functools import wraps
from collections import Counter
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.environ.get('DB_PATH', os.path.join(DATA_DIR, 'denis_snack.db'))
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_input(s, max_len=500):
    if not s: return ''
    s = str(s)[:max_len]
    return s.strip()

def weight_to_gram(label):
    """Parse weight label like '250g', '1kg', '1.5kg' into grams. -> None if invalid."""
    if not label:
        return None
    s = str(label).strip().lower().replace(' ', '')
    try:
        if 'kg' in s:
            return int(round(float(s.replace('kg', '')) * 1000))
        if 'g' in s:
            return int(round(float(s.replace('g', ''))))
        return int(round(float(s)))
    except (ValueError, TypeError):
        return None

def is_valid_email(e):
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', str(e)))

def is_valid_phone(p):
    return bool(re.match(r'^[0-9]{10,15}$', str(p)))

# Security headers + caching + compression
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
        "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'"
    )
    # Immutable assets (uuid-named uploads + static) can be cached aggressively
    if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
        response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
    # gzip-compress renderable responses > 1KB
    if (response.status_code == 200
            and 'gzip' in request.environ.get('HTTP_ACCEPT_ENCODING', '')
            and response.mimetype in ('text/html', 'application/json', 'text/plain', 'text/css', 'application/javascript')
            and response.content_length and response.content_length > 1024):
        data = gzip.compress(response.get_data(), 6)
        response.set_data(data)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Vary'] = 'Accept-Encoding'
    return response

@app.template_filter('fromjson')
def fromjson_filter(s):
    try: return json.loads(s)
    except: return []

@app.template_filter('format_rp')
def format_rp_filter(n):
    try: return f"Rp {int(n):,}".replace(",", ".")
    except: return "Rp 0"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'admin'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password TEXT NOT NULL,
        address TEXT,
        district TEXT,
        city TEXT,
        province TEXT,
        postal_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        emoji TEXT DEFAULT '📁',
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        base_price INTEGER NOT NULL DEFAULT 0,
        category_id INTEGER,
        emoji TEXT DEFAULT '🍿',
        photo TEXT,
        badge TEXT,
        is_active INTEGER DEFAULT 1,
        is_featured INTEGER DEFAULT 0,
        sku TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS product_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        weight_label TEXT NOT NULL,
        weight_gram INTEGER NOT NULL,
        price INTEGER NOT NULL,
        stock INTEGER DEFAULT 0,
        sku TEXT,
        min_stock INTEGER DEFAULT 5,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS stock_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_id INTEGER NOT NULL,
        change_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        note TEXT,
        admin_user TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT,
        customer_id INTEGER,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT,
        district TEXT,
        city TEXT,
        province TEXT,
        postal_code TEXT,
        items TEXT NOT NULL,
        subtotal INTEGER NOT NULL DEFAULT 0,
        shipping_cost INTEGER DEFAULT 0,
        discount INTEGER DEFAULT 0,
        total INTEGER NOT NULL,
        notes TEXT,
        status TEXT DEFAULT 'pending',
        payment_method TEXT,
        payment_status TEXT DEFAULT 'unpaid',
        payment_proof TEXT,
        payment_date TIMESTAMP,
        courier TEXT,
        tracking_number TEXT,
        shipping_status TEXT DEFAULT 'pending',
        shipped_at TIMESTAMP,
        delivered_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_status_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS promos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_type TEXT NOT NULL DEFAULT 'percent',
        discount_value INTEGER NOT NULL,
        min_purchase INTEGER DEFAULT 0,
        max_discount INTEGER DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        usage_limit INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bundles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        photo TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bundle_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bundle_id INTEGER NOT NULL,
        variant_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        FOREIGN KEY (bundle_id) REFERENCES bundles(id) ON DELETE CASCADE,
        FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    # Performance indexes on hot query columns
    for idx in [
        "CREATE INDEX IF NOT EXISTS ix_products_category ON products(category_id)",
        "CREATE INDEX IF NOT EXISTS ix_products_active ON products(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_products_featured ON products(is_featured)",
        "CREATE INDEX IF NOT EXISTS ix_variants_product ON product_variants(product_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_customer ON orders(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status)",
        "CREATE INDEX IF NOT EXISTS ix_orders_created ON orders(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_order_logs_order ON order_status_logs(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_stock_logs_variant ON stock_logs(variant_id)",
        "CREATE INDEX IF NOT EXISTS ix_cats_active ON categories(is_active)",
        "CREATE INDEX IF NOT EXISTS ix_customers_email ON customers(email)",
    ]:
        c.execute(idx)

    # Default admin
    if not c.execute("SELECT id FROM users WHERE username='admin'").fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                  ('admin', generate_password_hash('admin123'), 'admin'))

    # Default categories
    cats = [
        ('Keripik', 'keripik', 'Keripik renyah dan gurih', '🥔', 1, 1),
        ('Kue Kering', 'kue-kering', 'Kue kering berbagai rasa', '🍪', 1, 2),
        ('Permen', 'permen', 'Permen manis dan kenyal', '🍬', 1, 3),
        ('Snack', 'snack', 'Snack ringan sehari-hari', '🍿', 1, 4),
        ('Paket/Hampers', 'paket-hampers', 'Paket dan hampers spesial', '🎁', 1, 5),
        ('Lainnya', 'lainnya', 'Produk lainnya', '📁', 1, 6),
    ]
    for cat in cats:
        if not c.execute("SELECT id FROM categories WHERE slug=?", (cat[1],)).fetchone():
            c.execute("INSERT INTO categories (name, slug, description, emoji, is_active, sort_order) VALUES (?,?,?,?,?,?)", cat)

    # Default products + variants if empty
    if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        products = [
            ('Keripik Singkong Balado', 'Keripik singkong renyah dengan bumbu balado pedas', 12000, 'keripik', '🍠', 'Best Seller', 'KS-001'),
            ('Kue Kering Coklat', 'Kue kering coklat premium dengan taburan choco chips', 20000, 'kue-kering', '🍪', 'Baru', 'KK-001'),
            ('Permen Jelly Buah', 'Permen jelly rasa buah-buahan segar, lembut dan kenyal', 8000, 'permen', '🍬', None, 'PJ-001'),
            ('Kerupuk Udang', 'Kerupuk udang asli, renyah dan gurih khas', 15000, 'snack', '🍘', 'Best Seller', 'KU-001'),
            ('Keripik Kentang BBQ', 'Keripik kentang renyah dengan rasa BBQ smoky', 14000, 'keripik', '🥔', None, 'KK-002'),
            ('Nastar Nanas', 'Nastar isi selai nanas homemade, lembut dan lumer', 25000, 'kue-kering', '🥮', 'Favorit', 'NN-001'),
            ('Dodol Durian', 'Dodol durian legit khas, manis dan aroma durian kuat', 22000, 'snack', '🍡', None, 'DD-001'),
            ('Pilus Cikur', 'Pilus renyah dengan cita rasa cikur dan level pedas', 12000, 'snack', '🥢', 'Pedas', 'PC-001'),
        ]
        for p in products:
            c.execute("INSERT INTO products (name, description, base_price, category_id, emoji, badge, sku) VALUES (?,?,?,?,?,?,?)",
                (p[0], p[1], p[2], c.execute("SELECT id FROM categories WHERE slug=?", (p[3],)).fetchone()[0], p[4], p[5], p[6]))
            pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            base = p[2]
            variants = [
                (250, base, 100),
                (500, base * 2, 80),
                (750, int(base * 2.8), 50),
                (1000, base * 4, 30),
            ]
            for w, pr, st in variants:
                label = f"{w}g" if w < 1000 else "1kg"
                c.execute("INSERT INTO product_variants (product_id, weight_label, weight_gram, price, stock, sku, min_stock) VALUES (?,?,?,?,?,?,?)",
                    (pid, label, w, pr, st, f"{p[6]}-{w}", 5))

    # Default settings
    defaults = {'shop_name': 'Denis Snack', 'whatsapp': '6281234567890', 'address': 'Jl. Mawar No. 123, Jakarta Selatan', 'email': 'info@denissnack.com', 'shipping_fee_per_kg': '10000', 'wa_provider': 'fonnte', 'wa_api_key': '', 'wa_sender': '', 'wa_notify_admin': '1', 'wa_notify_customer': '1'}
    for k, v in defaults.items():
        if not c.execute("SELECT key FROM settings WHERE key=?", (k,)).fetchone():
            c.execute("INSERT INTO settings (key, value) VALUES (?,?)", (k, v))

    conn.commit()
    conn.close()

_settings_cache = {'data': None, 'ts': 0}

def get_settings():
    now = time.time()
    if _settings_cache['data'] is not None and now - _settings_cache['ts'] < 2:
        return _settings_cache['data']
    conn = get_db()
    s = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close()
    _settings_cache['data'] = s
    _settings_cache['ts'] = now
    return s

def invalidate_settings_cache():
    _settings_cache['data'] = None

# ═══════════════════════════════════════════════════════════
# THEME SYSTEM
# ═══════════════════════════════════════════════════════════
THEME_DEFAULTS = {
    'primary': '#FF6B35',
    'secondary': '#004E89',
    'accent': '#FFF200',
    'dark': '#1A1A2E',
    'light': '#FFF8F0',
    'success': '#10B981',
    'info': '#108AB1',
    'font_display': 'Poppins',
    'font_body': 'Inter',
    'logo_type': 'emoji',
    'logo_text': 'D',
    'logo_image': '',
    'bg_type': 'color',
    'bg_gradient_from': '#FFE4D6',
    'bg_gradient_to': '#FFF8F0',
    'bg_image': '',
    'hero_title': 'Nikmati Sensasi Camilan Lezat',
    'hero_subtitle': 'Keripik, kue kering, dan aneka snack renyah pilihan, dibuat segar untuk menemani setiap momenmu.',
    'hero_style': 'default',
    'hero_image': '',
    'button_style': 'rounded',
    'card_style': 'rounded',
    'product_cols': '4',
    'show_featured': '1',
    'animation': '1',
    'font_scale': 'normal',
}

COLOR_VALID = '#0123456789abcdefABCDEF'


def _norm_color(value, default):
    v = str(value or '').strip()
    if len(v) == 7 and v[0] == '#' and all(c in COLOR_VALID for c in v[1:]):
        return v
    if len(v) == 6 and all(c in COLOR_VALID for c in v):
        return '#' + v
    return default


def get_theme():
    s = get_settings()
    theme = {}
    for k, v in THEME_DEFAULTS.items():
        theme[k] = s.get('theme_' + k, v)
    for c in ('primary', 'secondary', 'accent', 'dark', 'light', 'success', 'info'):
        theme[c] = _norm_color(theme[c], THEME_DEFAULTS[c])
    if theme['font_scale'] not in ('small', 'normal', 'large'):
        theme['font_scale'] = 'normal'
    theme['product_cols'] = theme['product_cols'] if theme['product_cols'] in ('2', '3', '4') else '4'
    theme['body_class'] = 'theme-btn-{} theme-card-{} theme-font-{}'.format(
        theme['button_style'], theme['card_style'], theme['font_scale'])
    theme['body_class'] += ' theme-anim-off' if theme.get('animation') != '1' else ''
    return theme

@app.context_processor
def inject_globals():
    return {'theme': get_theme(), 'settings': get_settings()}

def gen_invoice_no():
    return f"DS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if not session.get('admin'):
            flash('Silakan login terlebih dahulu', 'error')
            return redirect(url_for('admin_login'))
        return f(*a, **kw)
    return d

# ═══════════════════════════════════════════════════════════
# CUSTOMER ROUTES
# ═══════════════════════════════════════════════════════════
@app.route('/')
def index():
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order").fetchall()
    cat_id = request.args.get('cat', '')
    search = sanitize_input(request.args.get('q', ''), 100)
    if cat_id and cat_id.isdigit():
        products = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1 AND p.category_id=? ORDER BY p.name", (int(cat_id),)).fetchall()
    elif search:
        products = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1 AND p.name LIKE ? ORDER BY p.name", (f'%{search}%',)).fetchall()
    else:
        products = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1 ORDER BY p.name").fetchall()
    featured = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1 AND p.is_featured=1 ORDER BY p.name").fetchall()
    promo = conn.execute("SELECT * FROM promos WHERE is_active=1 AND start_date <= date('now') AND (end_date IS NULL OR end_date >= date('now')) LIMIT 1").fetchone()
    settings = get_settings()
    conn.close()
    return render_template('index.html', products=products, categories=categories, featured=featured, promo=promo, settings=settings, search=search, cat_id=cat_id)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db()
    product = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return redirect(url_for('index'))
    variants = conn.execute("SELECT * FROM product_variants WHERE product_id=? AND is_active=1 ORDER BY weight_gram", (product_id,)).fetchall()
    settings = get_settings()
    related = conn.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1 AND p.category_id=? AND p.id!=? LIMIT 4", (product['category_id'], product_id)).fetchall()
    conn.close()
    return render_template('product_detail.html', product=product, variants=variants, settings=settings, related=related)

@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    data = request.json
    return jsonify({'success': True, 'message': 'Item ditambahkan ke keranjang'})

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'Data tidak valid'}), 400
    conn = get_db()
    customer_id = session.get('customer_id')
    customer_name = sanitize_input(data.get('name', ''), 100)
    phone = sanitize_input(data.get('phone', ''), 15)
    address = sanitize_input(data.get('address', ''), 500)
    district = sanitize_input(data.get('district', ''), 100)
    city = sanitize_input(data.get('city', ''), 100)
    province = sanitize_input(data.get('province', ''), 100)
    postal_code = sanitize_input(data.get('postal_code', ''), 10)
    # Validate required fields
    if not customer_name or not phone:
        return jsonify({'success': False, 'message': 'Nama dan telepon wajib diisi'}), 400
    if not is_valid_phone(phone.replace('+', '').replace('-', '')):
        return jsonify({'success': False, 'message': 'Nomor telepon tidak valid'}), 400
    if customer_id:
        cu = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        if cu:
            customer_name = customer_name or cu['name']
            phone = phone or cu['phone'] or ''
            address = address or cu['address'] or ''
            district = district or cu['district'] or ''
            city = city or cu['city'] or ''
            province = province or cu['province'] or ''
            postal_code = postal_code or cu['postal_code'] or ''
    items = data.get('items')
    # Validate items payload
    if not isinstance(items, list) or not items:
        return jsonify({'success': False, 'message': 'Keranjang kosong, tidak ada item untuk dipesan'}), 400
    cleaned = []
    for it in items:
        if not isinstance(it, dict):
            return jsonify({'success': False, 'message': 'Data item tidak valid'}), 400
        vid = it.get('variant_id')
        try:
            qty = int(it.get('qty', 1))
        except (TypeError, ValueError):
            qty = 0
        try:
            price = int(it.get('price', 0))
        except (TypeError, ValueError):
            price = 0
        if qty < 1:
            return jsonify({'success': False, 'message': 'Jumlah item tidak valid'}), 400
        if not vid:
            return jsonify({'success': False, 'message': 'Varian item tidak valid'}), 400
        cleaned.append({'product_id': it.get('product_id'), 'variant_id': vid, 'name': sanitize_input(it.get('name', ''), 100),
                        'price': price, 'qty': qty, 'emoji': sanitize_input(it.get('emoji', ''), 8), 'weight_label': sanitize_input(it.get('weight_label', ''), 20)})
    # Verify all variants exist and have enough stock BEFORE creating the order
    precheck = {}
    for it in cleaned:
        v = conn.execute("SELECT pv.id, pv.stock, p.name as pname FROM product_variants pv JOIN products p ON pv.product_id=p.id WHERE pv.id=? AND pv.is_active=1 AND p.is_active=1",
            (it['variant_id'],)).fetchone()
        if not v:
            conn.close()
            return jsonify({'success': False, 'message': f'Produk tidak tersedia (id varian {it["variant_id"]})'}), 400
        if v['stock'] < it['qty']:
            conn.close()
            return jsonify({'success': False, 'message': f'Stok tidak cukup untuk "{v["pname"]}" (stok: {v["stock"]})'}), 400
        precheck[it['variant_id']] = it['qty']
    subtotal = sum(i['price'] * i['qty'] for i in cleaned)
    shipping_cost = int(data.get('shipping_cost', 0))
    discount = int(data.get('discount', 0))
    if shipping_cost < 0 or discount < 0:
        conn.close()
        return jsonify({'success': False, 'message': 'Nilai ongkir/diskon tidak valid'}), 400
    total = subtotal + shipping_cost - discount
    if total < 0:
        total = 0
    invoice_no = gen_invoice_no()
    promo_code = data.get('promo_code', '')
    if promo_code:
        promo = conn.execute("SELECT * FROM promos WHERE code=? AND is_active=1", (promo_code,)).fetchone()
        if promo:
            conn.execute("UPDATE promos SET used_count=used_count+1 WHERE id=?", (promo['id'],))
    cur = conn.execute(
        """INSERT INTO orders (invoice_no, customer_id, customer_name, phone, address, district, city, province, postal_code,
           items, subtotal, shipping_cost, discount, total, notes, status, payment_method, payment_status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (invoice_no, customer_id, customer_name, phone, address, district, city, province, postal_code,
         json.dumps(cleaned), subtotal, shipping_cost, discount, total, data.get('notes', ''),
         'pending', data.get('payment_method', ''), 'unpaid')
    )
    order_id = cur.lastrowid
    conn.execute("INSERT INTO order_status_logs (order_id, old_status, new_status, note) VALUES (?,?,?,?)",
        (order_id, None, 'pending', 'Pesanan dibuat'))
    # Reduce stock
    for vid, qty in precheck.items():
        conn.execute("UPDATE product_variants SET stock=stock-? WHERE id=?", (qty, vid))
        conn.execute("INSERT INTO stock_logs (variant_id, change_type, quantity, note, admin_user) VALUES (?,?,?,?,?)",
            (vid, 'sale', -qty, f'Pesanan #{order_id}', 'system'))
    conn.commit()
    conn.close()
    # Send WhatsApp notifications (non-blocking)
    try:
        send_admin_order_notification(order_id, invoice_no, customer_name, total, cleaned)
    except Exception as e:
        app.logger.error(f"Admin WA notification failed: {e}")
    try:
        send_customer_order_confirmation(phone, invoice_no, customer_name, total, cleaned)
    except Exception as e:
        app.logger.error(f"Customer WA notification failed: {e}")
    return jsonify({'success': True, 'order_id': order_id, 'invoice_no': invoice_no})

@app.route('/api/promo/validate', methods=['POST'])
def validate_promo():
    data = request.json
    code = data.get('code', '')
    total = data.get('total', 0)
    conn = get_db()
    promo = conn.execute("SELECT * FROM promos WHERE code=? AND is_active=1", (code.upper(),)).fetchone()
    conn.close()
    if not promo:
        return jsonify({'valid': False, 'message': 'Kode promo tidak valid'})
    if promo['start_date'] and promo['start_date'] > datetime.now().strftime('%Y-%m-%d'):
        return jsonify({'valid': False, 'message': 'Promo belum berlaku'})
    if promo['end_date'] and promo['end_date'] < datetime.now().strftime('%Y-%m-%d'):
        return jsonify({'valid': False, 'message': 'Promo sudah expired'})
    if promo['usage_limit'] > 0 and promo['used_count'] >= promo['usage_limit']:
        return jsonify({'valid': False, 'message': 'Promo sudah habis digunakan'})
    if total < promo['min_purchase']:
        return jsonify({'valid': False, 'message': f'Minimal pembelian Rp {promo["min_purchase"]:,}'.replace(',', '.')})
    if promo['discount_type'] == 'percent':
        disc = int(total * promo['discount_value'] / 100)
        if promo['max_discount'] > 0:
            disc = min(disc, promo['max_discount'])
    else:
        disc = promo['discount_value']
    return jsonify({'valid': True, 'discount': disc, 'message': f'Diskon Rp {disc:,}'.replace(',', '.')})

@app.route('/api/shipping/cost', methods=['POST'])
def shipping_cost():
    data = request.json
    weight_gram = data.get('weight_gram', 0)
    settings = get_settings()
    per_kg = int(settings.get('shipping_fee_per_kg', 10000))
    kg = max(1, -(-weight_gram // 1000))
    cost = kg * per_kg
    return jsonify({'cost': cost, 'couriers': [
        {'name': 'JNE Regular', 'cost': cost, 'etd': '3-5 hari'},
        {'name': 'JNE Express', 'cost': int(cost * 1.5), 'etd': '1-2 hari'},
        {'name': 'SiCepat Reg', 'cost': int(cost * 0.9), 'etd': '2-4 hari'},
        {'name': 'AnterAja', 'cost': int(cost * 0.85), 'etd': '2-3 hari'},
    ]})

# ═══════════════════════════════════════════════════════════
# CUSTOMER AUTH
# ═══════════════════════════════════════════════════════════
@app.route('/register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', ''))
        email = sanitize_input(request.form.get('email', '')).lower()
        phone = sanitize_input(request.form.get('phone', ''))
        password = request.form.get('password', '')
        # Validation
        if not name or len(name) < 2:
            flash('Nama harus minimal 2 karakter', 'error')
            return render_template('customer_register.html')
        if not is_valid_email(email):
            flash('Format email tidak valid', 'error')
            return render_template('customer_register.html')
        if phone and not is_valid_phone(phone):
            flash('Nomor telepon tidak valid (10-15 digit angka)', 'error')
            return render_template('customer_register.html')
        if len(password) < 6:
            flash('Password harus minimal 6 karakter', 'error')
            return render_template('customer_register.html')
        conn = get_db()
        if conn.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone():
            flash('Email sudah terdaftar!', 'error')
            conn.close()
            return render_template('customer_register.html')
        conn.execute("INSERT INTO customers (name, email, phone, password) VALUES (?,?,?,?)",
                     (name, email, phone, generate_password_hash(password)))
        conn.commit()
        conn.close()
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('customer_login'))
    return render_template('customer_register.html')

@app.route('/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        email = sanitize_input(request.form.get('email', '')).lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email dan password harus diisi', 'error')
            return render_template('customer_login.html')
        conn = get_db()
        customer = conn.execute("SELECT * FROM customers WHERE email=?", (email,)).fetchone()
        conn.close()
        if customer and check_password_hash(customer['password'], password):
            session.clear()
            session.regenerate = True
            session['customer_id'] = customer['id']
            session['customer_name'] = customer['name']
            session['customer_email'] = customer['email']
            session.permanent = True
            return redirect(url_for('index'))
        flash('Email atau password salah!', 'error')
    return render_template('customer_login.html')

@app.route('/logout')
def customer_logout():
    for k in ['customer_id', 'customer_name', 'customer_email']:
        session.pop(k, None)
    return redirect(url_for('index'))

@app.route('/profile')
def customer_profile():
    if not session.get('customer_id'):
        return redirect(url_for('customer_login'))
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE id=?", (session['customer_id'],)).fetchone()
    orders = conn.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY created_at DESC", (session['customer_id'],)).fetchall()
    conn.close()
    return render_template('customer_profile.html', customer=customer, orders=orders)

@app.route('/my-orders/<int:order_id>')
def customer_order_detail(order_id):
    if not session.get('customer_id'):
        return redirect(url_for('customer_login'))
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=? AND customer_id=?", (order_id, session['customer_id'])).fetchone()
    if not order:
        conn.close()
        return redirect(url_for('customer_profile'))
    logs = conn.execute("SELECT * FROM order_status_logs WHERE order_id=? ORDER BY created_at", (order_id,)).fetchall()
    settings = get_settings()
    conn.close()
    return render_template('customer_order_detail.html', order=order, logs=logs, settings=settings)

# ═══════════════════════════════════════════════════════════
# ADMIN AUTH
# ═══════════════════════════════════════════════════════════
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username', ''))
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username dan password harus diisi', 'error')
            return render_template('admin_login.html')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session.clear()
            session.regenerate = True
            session['admin'] = True
            session['username'] = user['username']
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        flash('Username atau password salah', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ═══════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month_start = datetime.now().strftime('%Y-%m-01')
    total_products = conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    agg = conn.execute("""
        SELECT COUNT(*) as total_orders,
               COALESCE(SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END),0) as pending_orders,
               COALESCE(SUM(CASE WHEN payment_status='paid' THEN 1 ELSE 0 END),0) as paid_orders,
               COALESCE(SUM(CASE WHEN status NOT IN ('cancelled','refunded') THEN total ELSE 0 END),0) as total_revenue,
               COALESCE(SUM(CASE WHEN DATE(created_at)=? AND status NOT IN ('cancelled','refunded') THEN total ELSE 0 END),0) as today_revenue,
               COALESCE(SUM(CASE WHEN DATE(created_at)>=? AND status NOT IN ('cancelled','refunded') THEN total ELSE 0 END),0) as week_revenue,
               COALESCE(SUM(CASE WHEN DATE(created_at)>=? AND status NOT IN ('cancelled','refunded') THEN total ELSE 0 END),0) as month_revenue
        FROM orders""", (today, week_ago, month_start)).fetchone()
    stats = {
        'total_products': total_products,
        'total_orders': agg['total_orders'],
        'pending_orders': agg['pending_orders'],
        'paid_orders': agg['paid_orders'],
        'total_revenue': agg['total_revenue'],
        'today_revenue': agg['today_revenue'],
        'week_revenue': agg['week_revenue'],
        'month_revenue': agg['month_revenue'],
        'total_customers': total_customers,
    }
    low_stock = conn.execute("""SELECT pv.*, p.name as product_name FROM product_variants pv
        JOIN products p ON pv.product_id=p.id WHERE pv.is_active=1 AND pv.stock <= pv.min_stock ORDER BY pv.stock ASC LIMIT 10""").fetchall()
    recent_orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10").fetchall()
    # Top products computed in Python from order items JSON (no extra tables)
    name_map = {r['id']: r['name'] for r in conn.execute("SELECT id, name FROM products").fetchall()}
    sales_rows = conn.execute("SELECT items FROM orders WHERE status NOT IN ('cancelled','refunded') LIMIT 500").fetchall()
    cnt = Counter()
    for o in sales_rows:
        try:
            for it in json.loads(o['items']):
                cnt[name_map.get(it.get('product_id'))] += it.get('qty', 1)
        except Exception:
            continue
    top_products = [{'name': n, 'total_sold': q} for n, q in cnt.most_common(5) if n]
    notifications = []
    if agg['pending_orders'] > 0: notifications.append({'icon': '🛒', 'text': f"{agg['pending_orders']} pesanan baru menunggu diproses", 'url': '/admin/orders'})
    ns = conn.execute("SELECT COUNT(*) FROM product_variants WHERE is_active=1 AND stock <= min_stock").fetchone()[0]
    if ns > 0: notifications.append({'icon': '⚠️', 'text': f'{ns} produk stok hampir habis', 'url': '/admin/products'})
    conn.close()
    return render_template('admin_dashboard.html', stats=stats, orders=recent_orders, low_stock=low_stock, top_products=top_products, notifications=notifications)

# ═══════════════════════════════════════════════════════════
# ADMIN CATEGORIES
# ═══════════════════════════════════════════════════════════
@app.route('/admin/categories')
@admin_required
def admin_categories():
    conn = get_db()
    cats = conn.execute("SELECT c.*, (SELECT COUNT(*) FROM products WHERE category_id=c.id) as product_count FROM categories c ORDER BY c.sort_order").fetchall()
    conn.close()
    return render_template('admin_categories.html', categories=cats)

@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_category_add():
    conn = get_db()
    name = request.form['name']
    slug = name.lower().replace(' ', '-').replace('/', '-')
    desc = request.form.get('description', '')
    emoji = request.form.get('emoji', '📁')
    conn.execute("INSERT INTO categories (name, slug, description, emoji, sort_order) VALUES (?,?,?,?,?)",
        (name, slug, desc, emoji, conn.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM categories").fetchone()[0]))
    conn.commit()
    conn.close()
    flash('Kategori berhasil ditambahkan!', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/edit/<int:cat_id>', methods=['POST'])
@admin_required
def admin_category_edit(cat_id):
    conn = get_db()
    conn.execute("UPDATE categories SET name=?, description=?, emoji=? WHERE id=?",
        (request.form['name'], request.form.get('description', ''), request.form.get('emoji', '📁'), cat_id))
    conn.commit()
    conn.close()
    flash('Kategori berhasil diupdate!', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def admin_category_delete(cat_id):
    conn = get_db()
    conn.execute("UPDATE products SET category_id=NULL WHERE category_id=?", (cat_id,))
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()
    flash('Kategori berhasil dihapus!', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/toggle/<int:cat_id>', methods=['POST'])
@admin_required
def admin_category_toggle(cat_id):
    conn = get_db()
    c = conn.execute("SELECT is_active FROM categories WHERE id=?", (cat_id,)).fetchone()
    conn.execute("UPDATE categories SET is_active=? WHERE id=?", (0 if c['is_active'] else 1, cat_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_categories'))

# ═══════════════════════════════════════════════════════════
# ADMIN PRODUCTS
# ═══════════════════════════════════════════════════════════
@app.route('/admin/products')
@admin_required
def admin_products():
    conn = get_db()
    search = request.args.get('q', '')
    cat_filter = request.args.get('cat', '')
    query = "SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE 1=1"
    params = []
    if search:
        query += " AND (p.name LIKE ? OR p.sku LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if cat_filter:
        query += " AND p.category_id=?"
        params.append(cat_filter)
    query += " ORDER BY p.name"
    products = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
    conn.close()
    return render_template('admin_products.html', products=products, categories=categories, search=search, cat_filter=cat_filter)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_product_add():
    conn = get_db()
    if request.method == 'POST':
        photo = ''
        if 'photo' in request.files:
            f = request.files['photo']
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                photo = f"{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(UPLOAD_FOLDER, photo))
        cur = conn.execute(
            "INSERT INTO products (name, description, base_price, category_id, emoji, photo, badge, sku, is_active, is_featured) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (request.form['name'], request.form['description'], int(request.form.get('base_price', 0)),
             request.form.get('category_id') or None, request.form.get('emoji', '🍿'), photo,
             request.form.get('badge', ''), request.form.get('sku', ''),
             1 if request.form.get('is_active') else 0, 1 if request.form.get('is_featured') else 0))
        product_id = cur.lastrowid
        weights = request.form.getlist('variant_weight[]')
        prices = request.form.getlist('variant_price[]')
        stocks = request.form.getlist('variant_stock[]')
        skus = request.form.getlist('variant_sku[]')
        min_stocks = request.form.getlist('variant_min_stock[]')
        for i in range(len(weights)):
            wg = weight_to_gram(weights[i])
            if weights[i] and prices[i] and wg is not None:
                conn.execute("INSERT INTO product_variants (product_id, weight_label, weight_gram, price, stock, sku, min_stock) VALUES (?,?,?,?,?,?,?)",
                    (product_id, weights[i].strip(), wg, int(prices[i]),
                     int(stocks[i]) if i < len(stocks) and stocks[i] else 0,
                     skus[i] if i < len(skus) else '',
                     int(min_stocks[i]) if i < len(min_stocks) and min_stocks[i] else 5))
        conn.commit()
        conn.close()
        flash('Produk berhasil ditambahkan!', 'success')
        return redirect(url_for('admin_products'))
    categories = conn.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order").fetchall()
    conn.close()
    return render_template('admin_product_form.html', product=None, action='Tambah', categories=categories)

@app.route('/admin/products/edit/<int:pid>', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(pid):
    conn = get_db()
    if request.method == 'POST':
        photo = request.form.get('existing_photo', '')
        if 'photo' in request.files:
            f = request.files['photo']
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                photo = f"{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(UPLOAD_FOLDER, photo))
        conn.execute("UPDATE products SET name=?, description=?, base_price=?, category_id=?, emoji=?, photo=?, badge=?, sku=?, is_active=?, is_featured=? WHERE id=?",
            (request.form['name'], request.form['description'], int(request.form.get('base_price', 0)),
             request.form.get('category_id') or None, request.form.get('emoji', '🍿'), photo,
             request.form.get('badge', ''), request.form.get('sku', ''),
             1 if request.form.get('is_active') else 0, 1 if request.form.get('is_featured') else 0, pid))
        weights = request.form.getlist('variant_weight[]')
        prices = request.form.getlist('variant_price[]')
        stocks = request.form.getlist('variant_stock[]')
        skus = request.form.getlist('variant_sku[]')
        min_stocks = request.form.getlist('variant_min_stock[]')
        variant_ids = request.form.getlist('variant_id[]')
        for i in range(len(weights)):
            wg = weight_to_gram(weights[i])
            if weights[i] and prices[i] and wg is not None:
                vid = variant_ids[i] if i < len(variant_ids) and variant_ids[i] else None
                wl = weights[i].strip()
                if vid:
                    conn.execute("UPDATE product_variants SET weight_label=?, weight_gram=?, price=?, stock=?, sku=?, min_stock=? WHERE id=?",
                        (wl, wg, int(prices[i]), int(stocks[i]) if i < len(stocks) and stocks[i] else 0,
                         skus[i] if i < len(skus) else '', int(min_stocks[i]) if i < len(min_stocks) and min_stocks[i] else 5, vid))
                else:
                    conn.execute("INSERT INTO product_variants (product_id, weight_label, weight_gram, price, stock, sku, min_stock) VALUES (?,?,?,?,?,?,?)",
                        (pid, wl, wg, int(prices[i]), int(stocks[i]) if i < len(stocks) and stocks[i] else 0,
                         skus[i] if i < len(skus) else '', int(min_stocks[i]) if i < len(min_stocks) and min_stocks[i] else 5))
        conn.commit()
        conn.close()
        flash('Produk berhasil diupdate!', 'success')
        return redirect(url_for('admin_products'))
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    variants = conn.execute("SELECT * FROM product_variants WHERE product_id=? ORDER BY weight_gram", (pid,)).fetchall()
    categories = conn.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order").fetchall()
    conn.close()
    return render_template('admin_product_form.html', product=product, variants=variants, action='Edit', categories=categories)

@app.route('/admin/products/delete/<int:pid>', methods=['POST'])
@admin_required
def admin_product_delete(pid):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash('Produk berhasil dihapus!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/toggle/<int:pid>', methods=['POST'])
@admin_required
def admin_product_toggle(pid):
    conn = get_db()
    p = conn.execute("SELECT is_active FROM products WHERE id=?", (pid,)).fetchone()
    conn.execute("UPDATE products SET is_active=? WHERE id=?", (0 if p['is_active'] else 1, pid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_products'))

@app.route('/admin/products/featured/<int:pid>', methods=['POST'])
@admin_required
def admin_product_featured(pid):
    conn = get_db()
    p = conn.execute("SELECT is_featured FROM products WHERE id=?", (pid,)).fetchone()
    conn.execute("UPDATE products SET is_featured=? WHERE id=?", (0 if p['is_featured'] else 1, pid))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_products'))

# ═══════════════════════════════════════════════════════════
# ADMIN STOCK
# ═══════════════════════════════════════════════════════════
@app.route('/admin/stock')
@admin_required
def admin_stock():
    conn = get_db()
    variants = conn.execute("""SELECT pv.*, p.name as product_name, p.emoji,
        CASE WHEN pv.stock <= 0 THEN 'habis' WHEN pv.stock <= pv.min_stock THEN 'hampir_habis' ELSE 'tersedia' END as stock_status
        FROM product_variants pv JOIN products p ON pv.product_id=p.id WHERE pv.is_active=1 ORDER BY pv.stock ASC""").fetchall()
    conn.close()
    return render_template('admin_stock.html', variants=variants)

@app.route('/admin/stock/adjust', methods=['POST'])
@admin_required
def admin_stock_adjust():
    try:
        vid = int(request.form['variant_id'])
        qty = int(request.form['quantity'])
    except (ValueError, KeyError):
        flash('Data tidak valid', 'error')
        return redirect(url_for('admin_stock'))
    change_type = sanitize_input(request.form.get('type', 'adjustment'), 50)
    note = sanitize_input(request.form.get('note', ''), 200)
    if change_type not in ['adjustment', 'restock', 'return', 'correction']:
        change_type = 'adjustment'
    conn = get_db()
    conn.execute("UPDATE product_variants SET stock=stock+? WHERE id=?", (qty, vid))
    conn.execute("INSERT INTO stock_logs (variant_id, change_type, quantity, note, admin_user) VALUES (?,?,?,?,?)",
        (vid, change_type, qty, note, session.get('username', 'admin')))
    conn.commit()
    conn.close()
    flash('Stok berhasil diupdate!', 'success')
    return redirect(url_for('admin_stock'))

@app.route('/admin/stock/log/<int:vid>')
@admin_required
def admin_stock_log(vid):
    conn = get_db()
    variant = conn.execute("SELECT pv.*, p.name as product_name FROM product_variants pv JOIN products p ON pv.product_id=p.id WHERE pv.id=?", (vid,)).fetchone()
    logs = conn.execute("SELECT * FROM stock_logs WHERE variant_id=? ORDER BY created_at DESC LIMIT 50", (vid,)).fetchall()
    conn.close()
    return render_template('admin_stock_log.html', variant=variant, logs=logs)

# ═══════════════════════════════════════════════════════════
# ADMIN ORDERS
# ═══════════════════════════════════════════════════════════
@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn = get_db()
    status_filter = request.args.get('status', '')
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status=?"
        params.append(status_filter)
    query += " ORDER BY created_at DESC"
    orders = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin_orders.html', orders=orders, status_filter=status_filter)

@app.route('/admin/orders/<int:oid>')
@admin_required
def admin_order_detail(oid):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    logs = conn.execute("SELECT * FROM order_status_logs WHERE order_id=? ORDER BY created_at", (oid,)).fetchall()
    settings = get_settings()
    conn.close()
    if not order:
        flash('Pesanan tidak ditemukan', 'error')
        return redirect(url_for('admin_orders'))
    return render_template('admin_order_detail.html', order=order, logs=logs, settings=settings)

@app.route('/admin/orders/<int:oid>/status', methods=['POST'])
@admin_required
def admin_order_status(oid):
    new_status = sanitize_input(request.form.get('status', ''), 20)
    note = sanitize_input(request.form.get('note', ''), 500)
    valid_statuses = ['pending', 'paid', 'processing', 'shipped', 'completed', 'cancelled']
    if new_status not in valid_statuses:
        flash('Status tidak valid', 'error')
        return redirect(url_for('admin_order_detail', oid=oid))
    conn = get_db()
    old = conn.execute("SELECT status FROM orders WHERE id=?", (oid,)).fetchone()
    conn.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, oid))
    conn.execute("INSERT INTO order_status_logs (order_id, old_status, new_status, note) VALUES (?,?,?,?)",
        (oid, old['status'] if old else None, new_status, note))
    if new_status == 'cancelled':
        items = json.loads(conn.execute("SELECT items FROM orders WHERE id=?", (oid,)).fetchone()['items'])
        for item in items:
            vid = item.get('variant_id')
            if vid:
                conn.execute("UPDATE product_variants SET stock=stock+? WHERE id=?", (item.get('qty', 1), vid))
                conn.execute("INSERT INTO stock_logs (variant_id, change_type, quantity, note, admin_user) VALUES (?,?,?,?,?)",
                    (vid, 'return', item.get('qty', 1), f'Pesanan #{oid} dibatalkan', session.get('username', 'admin')))
    conn.commit()
    conn.close()
    flash('Status pesanan diupdate!', 'success')
    return redirect(url_for('admin_order_detail', oid=oid))

@app.route('/admin/orders/<int:oid>/payment', methods=['POST'])
@admin_required
def admin_order_payment(oid):
    payment_status = request.form['payment_status']
    conn = get_db()
    conn.execute("UPDATE orders SET payment_status=?, payment_date=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (payment_status, oid))
    conn.execute("INSERT INTO order_status_logs (order_id, old_status, new_status, note) VALUES (?,?,?,?)",
        (oid, 'payment', payment_status, f'Payment status diupdate ke {payment_status}'))
    conn.commit()
    conn.close()
    flash('Status pembayaran diupdate!', 'success')
    return redirect(url_for('admin_order_detail', oid=oid))

@app.route('/admin/orders/<int:oid>/shipping', methods=['POST'])
@admin_required
def admin_order_shipping(oid):
    conn = get_db()
    courier = request.form.get('courier', '')
    tracking = request.form.get('tracking_number', '')
    shipping_status = request.form.get('shipping_status', '')
    conn.execute("UPDATE orders SET courier=?, tracking_number=?, shipping_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (courier, tracking, shipping_status, oid))
    if shipping_status == 'shipped':
        conn.execute("UPDATE orders SET shipped_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
    elif shipping_status == 'delivered':
        conn.execute("UPDATE orders SET delivered_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
    conn.execute("INSERT INTO order_status_logs (order_id, old_status, new_status, note) VALUES (?,?,?,?)",
        (oid, 'shipping', shipping_status, f'Kurir: {courier}, Resi: {tracking}'))
    conn.commit()
    conn.close()
    flash('Info pengiriman diupdate!', 'success')
    return redirect(url_for('admin_order_detail', oid=oid))

@app.route('/admin/orders/<int:oid>/invoice')
@admin_required
def admin_order_invoice(oid):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    settings = get_settings()
    conn.close()
    return render_template('invoice.html', order=order, settings=settings)

# ═══════════════════════════════════════════════════════════
# ADMIN CUSTOMERS
# ═══════════════════════════════════════════════════════════
@app.route('/admin/customers')
@admin_required
def admin_customers():
    conn = get_db()
    customers = conn.execute("""SELECT c.*,
        (SELECT COUNT(*) FROM orders WHERE customer_id=c.id) as order_count,
        (SELECT COALESCE(SUM(total),0) FROM orders WHERE customer_id=c.id AND status NOT IN ('cancelled','refunded')) as total_spent,
        (SELECT created_at FROM orders WHERE customer_id=c.id ORDER BY created_at DESC LIMIT 1) as last_order
        FROM customers c ORDER BY c.created_at DESC""").fetchall()
    conn.close()
    return render_template('admin_customers.html', customers=customers)

@app.route('/admin/customers/<int:cid>')
@admin_required
def admin_customer_detail(cid):
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    orders = conn.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY created_at DESC", (cid,)).fetchall()
    conn.close()
    return render_template('admin_customer_detail.html', customer=customer, orders=orders)

@app.route('/admin/customers/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def admin_customer_edit(cid):
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    if not customer:
        conn.close()
        flash('Pelanggan tidak ditemukan', 'error')
        return redirect(url_for('admin_customers'))
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', ''), 100)
        email = sanitize_input(request.form.get('email', '')).lower()
        phone = sanitize_input(request.form.get('phone', ''), 20)
        address = sanitize_input(request.form.get('address', ''), 500)
        district = sanitize_input(request.form.get('district', ''), 100)
        city = sanitize_input(request.form.get('city', ''), 100)
        province = sanitize_input(request.form.get('province', ''), 100)
        postal_code = sanitize_input(request.form.get('postal_code', ''), 10)
        conn.close()
        if not name or len(name) < 2:
            flash('Nama harus minimal 2 karakter', 'error')
            return redirect(url_for('admin_customer_edit', cid=cid))
        if email and not is_valid_email(email):
            flash('Format email tidak valid', 'error')
            return redirect(url_for('admin_customer_edit', cid=cid))
        if not email:
            flash('Email wajib diisi', 'error')
            return redirect(url_for('admin_customer_edit', cid=cid))
        if phone and not is_valid_phone(phone):
            flash('Nomor telepon tidak valid (10-15 digit angka)', 'error')
            return redirect(url_for('admin_customer_edit', cid=cid))
        conn = get_db()
        dup = conn.execute("SELECT id FROM customers WHERE email=? AND id!=?", (email, cid)).fetchone()
        if dup:
            conn.close()
            flash('Email sudah digunakan pelanggan lain', 'error')
            return redirect(url_for('admin_customer_edit', cid=cid))
        conn.execute("""UPDATE customers SET name=?, email=?, phone=?, address=?, district=?, city=?, province=?, postal_code=? WHERE id=?""",
            (name, email, phone, address, district, city, province, postal_code, cid))
        conn.commit()
        conn.close()
        flash('Data pelanggan berhasil diperbarui.', 'success')
        return redirect(url_for('admin_customer_detail', cid=cid))
    conn.close()
    return render_template('admin_customer_edit.html', customer=customer)

# ═══════════════════════════════════════════════════════════
# ADMIN PROMOS
# ═══════════════════════════════════════════════════════════
@app.route('/admin/promos')
@admin_required
def admin_promos():
    conn = get_db()
    promos = conn.execute("SELECT * FROM promos ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('admin_promos.html', promos=promos)

@app.route('/admin/promos/add', methods=['POST'])
@admin_required
def admin_promo_add():
    conn = get_db()
    conn.execute("""INSERT INTO promos (code, discount_type, discount_value, min_purchase, max_discount, start_date, end_date, usage_limit, is_active)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (request.form['code'].upper(), request.form['discount_type'], int(request.form['discount_value']),
         int(request.form.get('min_purchase', 0)), int(request.form.get('max_discount', 0)),
         request.form.get('start_date') or None, request.form.get('end_date') or None,
         int(request.form.get('usage_limit', 0)), 1 if request.form.get('is_active') else 0))
    conn.commit()
    conn.close()
    flash('Promo berhasil ditambahkan!', 'success')
    return redirect(url_for('admin_promos'))

@app.route('/admin/promos/edit/<int:pid>', methods=['POST'])
@admin_required
def admin_promo_edit(pid):
    conn = get_db()
    conn.execute("""UPDATE promos SET code=?, discount_type=?, discount_value=?, min_purchase=?, max_discount=?,
        start_date=?, end_date=?, usage_limit=?, is_active=? WHERE id=?""",
        (request.form['code'].upper(), request.form['discount_type'], int(request.form['discount_value']),
         int(request.form.get('min_purchase', 0)), int(request.form.get('max_discount', 0)),
         request.form.get('start_date') or None, request.form.get('end_date') or None,
         int(request.form.get('usage_limit', 0)), 1 if request.form.get('is_active') else 0, pid))
    conn.commit()
    conn.close()
    flash('Promo berhasil diupdate!', 'success')
    return redirect(url_for('admin_promos'))

@app.route('/admin/promos/delete/<int:pid>', methods=['POST'])
@admin_required
def admin_promo_delete(pid):
    conn = get_db()
    conn.execute("DELETE FROM promos WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash('Promo berhasil dihapus!', 'success')
    return redirect(url_for('admin_promos'))

# ═══════════════════════════════════════════════════════════
# ADMIN REPORTS
# ═══════════════════════════════════════════════════════════
@app.route('/admin/reports')
@admin_required
def admin_reports():
    conn = get_db()
    period = request.args.get('period', 'daily')
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month_start = datetime.now().strftime('%Y-%m-01')
    if period == 'daily':
        start = today
        sales = conn.execute("SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total) as revenue FROM orders WHERE DATE(created_at)=? AND status NOT IN ('cancelled','refunded') GROUP BY DATE(created_at)", (today,)).fetchall()
    elif period == 'weekly':
        start = week_ago
        sales = conn.execute("SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total) as revenue FROM orders WHERE DATE(created_at)>=? AND status NOT IN ('cancelled','refunded') GROUP BY DATE(created_at) ORDER BY date", (week_ago,)).fetchall()
    else:
        start = month_start
        sales = conn.execute("SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total) as revenue FROM orders WHERE DATE(created_at)>=? AND status NOT IN ('cancelled','refunded') GROUP BY DATE(created_at) ORDER BY date", (month_start,)).fetchall()
    total_revenue = sum(r['revenue'] or 0 for r in sales)
    total_orders = sum(r['orders'] for r in sales)
    # Top products computed in Python from order items JSON
    meta = {r['id']: {'name': r['name'], 'emoji': r['emoji']} for r in conn.execute("SELECT id, name, emoji FROM products").fetchall()}
    sales_rows = conn.execute("SELECT items FROM orders WHERE DATE(created_at)>=? AND status NOT IN ('cancelled','refunded')", (start,)).fetchall()
    cnt = Counter()
    revenue_map = {}
    for o in sales_rows:
        try:
            for it in json.loads(o['items']):
                pid = it.get('product_id')
                if pid not in meta:
                    continue
                cnt[pid] += it.get('qty', 1)
                revenue_map[pid] = revenue_map.get(pid, 0) + it.get('price', 0) * it.get('qty', 1)
        except Exception:
            continue
    top_products = [{'name': meta[pid]['name'], 'emoji': meta[pid]['emoji'], 'qty': cnt[pid], 'revenue': revenue_map.get(pid, 0)}
                    for pid, _ in cnt.most_common(10)]
    conn.close()
    return render_template('admin_reports.html', sales=sales, period=period, total_revenue=total_revenue, total_orders=total_orders, top_products=top_products)

# ═══════════════════════════════════════════════════════════
# ADMIN SETTINGS
# ═══════════════════════════════════════════════════════════
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    conn = get_db()
    if request.method == 'POST':
        for key in ['shop_name', 'whatsapp', 'address', 'email', 'shipping_fee_per_kg', 'wa_provider', 'wa_api_key', 'wa_sender', 'wa_notify_admin', 'wa_notify_customer']:
            value = request.form.get(key, '')
            if key in ('wa_notify_admin', 'wa_notify_customer'):
                value = '1' if value == 'on' else '0'
            if conn.execute("SELECT key FROM settings WHERE key=?", (key,)).fetchone():
                conn.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
            else:
                conn.execute("INSERT INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()
        invalidate_settings_cache()
        flash('Pengaturan berhasil disimpan!', 'success')
    settings = get_settings()
    conn.close()
    return render_template('admin_settings.html', settings=settings)

@app.route('/admin/theme', methods=['GET', 'POST'])
@admin_required
def admin_theme():
    conn = get_db()
    if request.method == 'POST':
        for key, default in THEME_DEFAULTS.items():
            value = request.form.get(key, str(default))
            if key in ('primary', 'secondary', 'accent', 'dark', 'light', 'success', 'info'):
                value = _norm_color(value, default)
            if key in ('animation', 'show_featured'):
                value = '1' if value == 'on' else '0'
            if conn.execute("SELECT key FROM settings WHERE key=?", ('theme_' + key,)).fetchone():
                conn.execute("UPDATE settings SET value=? WHERE key=?", (value, 'theme_' + key))
            else:
                conn.execute("INSERT INTO settings (key, value) VALUES (?,?)", ('theme_' + key, value))
        conn.commit()
        invalidate_settings_cache()
        flash('Tema website berhasil disimpan!', 'success')
        conn.close()
        return redirect(url_for('admin_theme'))
    theme = get_theme()
    conn.close()
    return render_template('admin_theme.html', theme=theme)

@app.route('/admin/theme/reset', methods=['POST'])
@admin_required
def admin_theme_reset():
    conn = get_db()
    for key in THEME_DEFAULTS:
        if conn.execute("SELECT key FROM settings WHERE key=?", ('theme_' + key,)).fetchone():
            conn.execute("DELETE FROM settings WHERE key=?", ('theme_' + key,))
    conn.commit()
    conn.close()
    invalidate_settings_cache()
    flash('Tema telah dikembalikan ke default.', 'success')
    return redirect(url_for('admin_theme'))

@app.route('/admin/theme/upload', methods=['POST'])
@admin_required
def admin_theme_upload():
    ftype = request.form.get('type', 'image')  # 'image' | 'logo'
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Tidak ada file'}), 400
    f = request.files['file']
    if f and f.filename and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        filename = f"theme_{ftype}_{uuid.uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        f.save(path)
        return jsonify({'success': True, 'filename': filename})
    return jsonify({'success': False, 'message': 'File tidak valid'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Prevent path traversal
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, safe_name)

# ═══════════════════════════════════════════════════════════
# WHATSAPP NOTIFICATION SERVICE
# ═══════════════════════════════════════════════════════════

def send_whatsapp(to, message, settings=None):
    """Send WhatsApp message via configured provider.
    Returns (success: bool, response: dict)"""
    if settings is None:
        settings = get_settings()
    
    provider = settings.get('wa_provider', 'fonnte')
    api_key = settings.get('wa_api_key', '')
    sender = settings.get('wa_sender', '')
    
    if not api_key:
        return False, {'error': 'API Key tidak dikonfigurasi'}
    
    # Format phone number
    to = to.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if to.startswith('0'):
        to = '62' + to[1:]
    elif to.startswith('+62'):
        to = to[1:]
    elif not to.startswith('62'):
        to = '62' + to
    
    payload = {
        'target': to,
        'message': message,
    }
    if sender:
        payload['sender'] = sender
    
    try:
        if provider == 'fonnte':
            return _send_fonnte(payload, api_key)
        elif provider == 'wablas':
            return _send_wablas(payload, api_key, settings.get('wa_device_id', ''))
        elif provider == 'custom':
            return _send_custom_webhook(payload, api_key, settings.get('wa_webhook_url', ''))
        else:
            return False, {'error': f'Provider tidak dikenal: {provider}'}
    except Exception as e:
        return False, {'error': str(e)}

def _send_fonnte(payload, api_key):
    """Send via Fonnte (https://fonnte.com)"""
    url = 'https://api.fonnte.com/send'
    headers = {'Authorization': api_key}
    response = requests.post(url, data=payload, headers=headers, timeout=10)
    result = response.json()
    success = result.get('status') == True or result.get('status') == 'success'
    return success, result

def _send_wablas(payload, api_key, device_id):
    """Send via Wablas (https://wablas.com)"""
    if not device_id:
        return False, {'error': 'Device ID diperlukan untuk Wablas'}
    url = f'https://wablas.com/api/send-message?token={api_key}&device={device_id}'
    response = requests.post(url, data=payload, timeout=10)
    result = response.json()
    success = result.get('status') == 'success'
    return success, result

def _send_custom_webhook(payload, api_key, webhook_url):
    """Send via custom webhook"""
    if not webhook_url:
        return False, {'error': 'Webhook URL tidak dikonfigurasi'}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
    try:
        result = response.json()
    except:
        result = {'raw': response.text}
    success = response.status_code == 200
    return success, result

def send_admin_order_notification(order_id, invoice_no, customer_name, total, items, settings=None):
    """Send WhatsApp notification to admin for new order"""
    if settings is None:
        settings = get_settings()
    
    if settings.get('wa_notify_admin') != '1':
        return False, {'skipped': 'Admin notification disabled'}
    
    admin_phone = settings.get('whatsapp', '6281234567890')
    
    item_lines = '\n'.join([f"  - {i['name']} ({i['weight_label']}) x{i['qty']} = Rp {i['price'] * i['qty']:,}".replace(',', '.') for i in items])
    
    message = f"""🔔 *PESANAN BARU*
    
📋 Invoice: {invoice_no}
👤 Pelanggan: {customer_name}
💰 Total: Rp {total:,}
📦 Item:
{item_lines}

🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}
    
Kelola di: {request.host_url if request else ''}admin/orders/{order_id}"""
    
    return send_whatsapp(admin_phone, message, settings)

def send_customer_order_confirmation(phone, invoice_no, customer_name, total, items, settings=None):
    """Send WhatsApp confirmation to customer"""
    if settings is None:
        settings = get_settings()
    
    if settings.get('wa_notify_customer') != '1':
        return False, {'skipped': 'Customer notification disabled'}
    
    item_lines = '\n'.join([f"  {i['name']} ({i['weight_label']}) x{i['qty']}" for i in items])
    
    message = f"""✅ *KONFIRMASI PESANAN*
    
Halo {customer_name}, pesanan Anda sudah kami terima!

📋 Invoice: {invoice_no}
💰 Total: Rp {total:,}
📦 Item:
{item_lines}

🚚 Status: Menunggu Konfirmasi
🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}

Terima kasih telah berbelanja di {settings.get('shop_name', 'Denis Snack')}!
Hubungi kami via WhatsApp ini jika ada pertanyaan."""
    
    return send_whatsapp(phone, message, settings)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
