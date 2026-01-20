import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tabla Productos
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE,
        name TEXT,
        category TEXT,
        unit_price REAL,
        price_dozen REAL,
        price_hundred REAL,
        import_cost REAL
    )''')
    
    # 2. Tabla Almacenes
    c.execute('''CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY,
        name TEXT,
        location TEXT
    )''')
    
    # 3. Tabla Inventario
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        warehouse_id INTEGER,
        quantity INTEGER,
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id)
    )''')
    
    # 4. Tabla Kardex
    c.execute('''CREATE TABLE IF NOT EXISTS kardex (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        product_id INTEGER,
        warehouse_id INTEGER,
        movement_type TEXT,
        reason TEXT,
        quantity INTEGER
    )''')
    
    # 5. Tabla Ventas
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        date TEXT,
        total_amount REAL,
        items_json TEXT,
        status TEXT
    )''')

    # 6. Tabla Usuarios (PARA EL LOGIN)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )''')
    
    # Crear admin por defecto si no existe
    try:
        c.execute("SELECT count(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
    except:
        pass

    conn.commit()
    conn.close()

def run_query(query, params=()):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        conn.close()
        return c.lastrowid
    except Exception as e:
        return None

# ESTA ES LA PARTE CORREGIDA (params=None)
def get_data(query, params=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        if params:
            df = pd.read_sql(query, conn, params=params)
        else:
            df = pd.read_sql(query, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

init_db()
