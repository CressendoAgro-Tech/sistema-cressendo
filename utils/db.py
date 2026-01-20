import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join("data", "erp.db")

def get_connection():
    """Returns a connection to the SQLite database."""
    if not os.path.exists("data"):
        os.makedirs("data")
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    """Initializes the database with necessary tables."""
    conn = get_connection()
    c = conn.cursor()

    # --- MODULE 1: COMMERCIAL ---
    # Products
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE,
        name TEXT,
        category TEXT,
        unit_price REAL,
        stock INTEGER DEFAULT 0
    )''')
    
    # Warehouses
    c.execute('''CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        location TEXT
    )''')

    # Inventory (Stock per warehouse)
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        warehouse_id INTEGER,
        quantity INTEGER,
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id)
    )''')

    # Quotes
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        date TEXT,
        total_amount REAL,
        status TEXT DEFAULT 'Pending', -- Pending, Invoiced
        items_json TEXT -- Storing items as JSON for simplicity in prototype
    )''')

    # Sales
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER,
        customer_name TEXT,
        date TEXT,
        total_amount REAL,
        payment_method TEXT,
        warehouse_id INTEGER,
        FOREIGN KEY(quote_id) REFERENCES quotes(id)
    )''')

    # --- MODULE 2: LOGISTICS ---
    # Imports
    c.execute('''CREATE TABLE IF NOT EXISTS imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dam_number TEXT,
        arrival_date TEXT,
        fob_total REAL,
        freight REAL,
        insurance REAL,
        ad_valorem_rate REAL,
        exchange_rate REAL,
        status TEXT DEFAULT 'Draft'
    )''')

    # Import Items (Linked to an Import)
    c.execute('''CREATE TABLE IF NOT EXISTS import_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id INTEGER,
        product_name TEXT,
        hs_code TEXT,
        quantity INTEGER,
        fob_unit REAL,
        FOREIGN KEY(import_id) REFERENCES imports(id)
    )''')

    # --- MODULE 3: HR ---
    # Employees
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        dni TEXT UNIQUE,
        start_date TEXT,
        salary REAL,
        family_allowance BOOLEAN,
        pension_system TEXT, -- AFP-Habitat, ONP, etc.
        commission_type TEXT -- Flujo, Mixta
    )''')

    # --- MODULE 4: ACCOUNTING ---
    # Purchase Invoices (Registro de Compras)
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        provider TEXT,
        ruc TEXT,
        doc_type TEXT, -- Factura, Boleta, DAM
        series TEXT,
        number TEXT,
        base_amount REAL,
        igv_amount REAL,
        total_amount REAL,
        file_path TEXT, -- Path to saved PDF in documentos_sustento
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT -- Admin, Vendedor
    )''')

    # --- ADVANCED LOGISTICS ---
    # Migration for Wholesale Prices
    try:
        c.execute("ALTER TABLE products ADD COLUMN price_dozen REAL DEFAULT 0")
        c.execute("ALTER TABLE products ADD COLUMN price_hundred REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Kardex (Audit History)
    c.execute('''CREATE TABLE IF NOT EXISTS kardex (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        product_id INTEGER,
        warehouse_id INTEGER,
        movement_type TEXT, -- ENTRADA, SALIDA, TRANSFERENCIA
        reason TEXT, -- Compra / Venta / Merma / Transferencia / Ajuste
        quantity INTEGER,
        balance INTEGER DEFAULT 0, -- To be calculated or just stored
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id)
    )''')

    # --- CRITICAL IMPROVEMENTS ---
    # Migration for doc_type in sales
    try:
        c.execute("ALTER TABLE sales ADD COLUMN doc_type TEXT DEFAULT 'Nota de Venta'")
    except sqlite3.OperationalError:
        pass

    # Messages (Internal Chat)
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        username TEXT,
        message TEXT,
        is_urgent BOOLEAN DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # --- MODULE 4: HR & PAYROLL ---
    # Employees
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        dni TEXT UNIQUE,
        role TEXT, -- Admin, Vendedor, Logistica, RRHH
        start_date TEXT,
        base_salary REAL,
        family_allowance BOOLEAN DEFAULT 0, -- Asignacion Familiar
        pension_system TEXT -- ONP, AFP_INTEGRA, AFP_PRIMA, AFP_HABITAT, AFP_PROFUTURO
    )''')

    # Payroll (Planilla)
    c.execute('''CREATE TABLE IF NOT EXISTS payroll (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        period TEXT, -- YYYY-MM
        days_worked INTEGER DEFAULT 30,
        base_salary REAL,
        fam_allowance_amt REAL,
        total_income REAL,
        
        pension_system TEXT, 
        pension_amt REAL,
        renta_5ta REAL,
        
        net_pay REAL,
        
        essalud REAL,
        
        processed_date TEXT,
        FOREIGN KEY(employee_id) REFERENCES employees(id)
    )''')

    # Default Users
    users = [
        ("admin", "gerente2026", "Admin"),
        ("vendedor", "caja1", "Vendedor")
    ]
    for u, p, r in users:
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (u, p, r))
        except sqlite3.IntegrityError:
            pass # User already exists

    conn.commit()
    conn.close()

def run_query(query, params=()):
    """Executes a query and returns the result."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def get_data(query, params=()):
    """Executes a select query and returns a pandas DataFrame."""
    conn = get_connection()
    try:
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()
    return df
