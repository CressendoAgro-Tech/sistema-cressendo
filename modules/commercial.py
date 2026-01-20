import streamlit as st
import pandas as pd
from utils.db import run_query, get_data
import json
from datetime import datetime

def app():
    st.title("Sistema Comercial y POS")

    # Menú interno
    menu = st.tabs(["🛒 Punto de Venta / Cotizador", "📜 Historial", "📦 Inventario y Almacenes"])

    # --- PESTAÑA 1: POS y COTIZACIONES ---
    with menu[0]:
        st.header("Nueva Operación")
        
        # Modo de operación
        mode = st.radio("Tipo de Operación:", ["🛒 Venta Directa", "📄 Crear Cotización"], horizontal=True)

        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col1, col2 = st.columns([2, 1])
        
        with col1:
            client = st.text_input("Cliente", value="Cliente General")
            doc_type = st.selectbox("Documento", ["Nota de Venta", "Boleta", "Factura"])
            
            st.divider()
            st.subheader("🔍 Buscar Producto")
            search_term = st.text_input("Escribe nombre o código", placeholder="Ej: Bebedero...")
            
            # Buscar productos
            query = """
            SELECT p.id, p.name, p.unit_price, p.price_dozen, p.price_hundred, IFNULL(i.quantity, 0) as stock 
            FROM products p 
            LEFT JOIN inventory i ON p.id = i.product_id 
            WHERE p.name LIKE ? OR p.sku LIKE ? LIMIT 5
            """
            products = get_data(query, ('%' + search_term + '%', '%' + search_term + '%'))

            if not products.empty and search_term:
                for index, row in products.iterrows():
                    with st.expander(f"{row['name']} | Stock: {row['stock']}"):
                        # Selección de precio dinámico
                        price_opts = {
                            f"Unidad (S/. {row['unit_price']})": row['unit_price'],
                            f"Docena (S/. {row['price_dozen']})": row['price_dozen'],
                            f"Ciento (S/. {row['price_hundred']})": row['price_hundred']
                        }
                        # Filtrar precios None
                        price_opts = {k: v for k, v in price_opts.items() if v is not None}
                        
                        selected_price_label = st.selectbox("Precio a aplicar:", list(price_opts.keys()), key=f"p_sel_{row['id']}")
                        final_price = price_opts[selected_price_label]
                        
                        qty = st.number_input("Cantidad", min_value=1, key=f"q_{row['id']}")
                        
                        if st.button("Añadir al Carrito", key=f"add_{row['id']}"):
                            item = {
                                "id": row['id'],
                                "name": row['name'],
                                "price": final_price,
                                "qty": qty,
                                "total": final_price * qty
                            }
                            st.session_state.cart.append(item)
                            st.rerun()

        # --- CARRITO (DERECHA) ---
        with col2:
            st.subheader("📝 Resumen")
            if len(st.session_state.cart) > 0:
                total_sale = 0
                for i, item in enumerate(st.session_state.cart):
                    st.write(f"**{item['qty']} x {item['name']}**")
                    st.write(f"S/. {item['total']:.2f}")
                    total_sale += item['total']
                    if st.button("🗑️", key=f"del_{i}"):
                        st.session_state.cart.pop(i)
                        st.rerun()
                    st.divider()
                
                st.metric("TOTAL", f"S/. {total_sale:.2f}")
                
                btn_text = "✅ Finalizar VENTA" if mode == "🛒 Venta Directa" else "💾 Guardar COTIZACIÓN"
                
                if st.button(btn_text, type="primary", use_container_width=True):
                    items_json = json.dumps(st.session_state.cart)
                    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    status = 'VENDIDO' if mode == "🛒 Venta Directa" else 'COTIZACION'
                    
                    # Guardar en Historial (Quotes)
                    run_query("INSERT INTO quotes (customer_name, date, total_amount, items_json, status) VALUES (?, ?, ?, ?, ?)", 
                              (client, date_now, total_sale, items_json, status))
                    
                    # Si es VENTA, descontamos stock
                    if status == 'VENDIDO':
                        for item in st.session_state.cart:
                            run_query("UPDATE inventory SET quantity = quantity - ? WHERE product_id = ? AND warehouse_id = 1", (item['qty'], item['id']))
                        st.success("¡Venta registrada y stock actualizado!")
                    else:
                        st.success("¡Cotización guardada correctamente!")
                    
                    st.session_state.cart = []
                    st.balloons()
                    st.rerun()

    # --- PESTAÑA 2: HISTORIAL ---
    with menu[1]:
        st.header("Historial de Transacciones")
        sales = get_data("SELECT id, date, customer_name, total_amount, status FROM quotes ORDER BY id DESC")
        st.dataframe(sales, use_container_width=True)

    # --- PESTAÑA 3: INVENTARIO (CON CORRECCIÓN DE PRECIOS) ---
    with menu[2]:
        st.header("Inventario")
        inv_tabs = st.tabs(["Stock", "Carga Masiva"])
        
        with inv_tabs[0]:
            df_stock = get_data("""
                SELECT p.sku, p.name, IFNULL(i.quantity, 0) as stock, 
                p.unit_price, p.price_dozen, p.price_hundred, p.import_cost 
                FROM products p 
                LEFT JOIN inventory i ON p.id = i.product_id
            """)
            st.dataframe(df_stock, use_container_width=True)
            
        with inv_tabs[1]:
            st.write("### Subir Excel (Con todos los precios)")
            uploaded_file = st.file_uploader("Sube tu Excel aquí", type=['xlsx'])
            if uploaded_file:
                df = pd.read_excel(uploaded_file)
                st.write("Columnas detectadas:", list(df.columns))
                
                c1, c2, c3 = st.columns(3)
                col_name = c1.selectbox("Columna Nombre", df.columns)
                col_stock = c2.selectbox("Columna Stock", df.columns)
                col_cost = c3.selectbox("Columna Costo", ["(Vacío)"] + list(df.columns))
                
                c4, c5, c6 = st.columns(3)
                col_price = c4.selectbox("Precio Unidad", df.columns)
                col_dozen = c5.selectbox("Precio Docena", ["(Vacío)"] + list(df.columns))
                col_hundred = c6.selectbox("Precio Ciento", ["(Vacío)"] + list(df.columns))
                
                if st.button("🚀 PROCESAR DATOS"):
                    for index, row in df.iterrows():
                        if pd.isna(row[col_name]): continue
                        
                        name = str(row[col_name])
                        stock = int(row[col_stock]) if pd.notna(row[col_stock]) else 0
                        p_unit = float(row[col_price]) if pd.notna(row[col_price]) else 0
                        
                        # Precios opcionales
                        p_dozen = float(row[col_dozen]) if col_dozen != "(Vacío)" and pd.notna(row[col_dozen]) else None
                        p_hundred = float(row[col_hundred]) if col_hundred != "(Vacío)" and pd.notna(row[col_hundred]) else None
                        cost = float(row[col_cost]) if col_cost != "(Vacío)" and pd.notna(row[col_cost]) else 0
                        
                        # Insertar Producto (Con todos los precios)
                        run_query("""
                            INSERT OR IGNORE INTO products (sku, name, unit_price, price_dozen, price_hundred, import_cost) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (name, name, p_unit, p_dozen, p_hundred, cost))
                        
                        # Actualizar Inventario
                        prod_id_df = get_data("SELECT id FROM products WHERE sku = ?", (name,))
                        if not prod_id_df.empty:
                            pid = prod_id_df.iloc[0]['id']
                            run_query("INSERT OR IGNORE INTO inventory (product_id, warehouse_id, quantity) VALUES (?, 1, ?)", (pid, stock))
                            run_query("UPDATE inventory SET quantity = ? WHERE product_id = ?", (stock, pid))
                            
                    st.success("¡Carga completa con precios!")
                    st.rerun()
