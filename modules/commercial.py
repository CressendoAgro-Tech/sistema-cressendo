import streamlit as st
import pandas as pd
from utils.db import run_query, get_data
import json
from datetime import datetime

def app():  # <--- ESTA ES LA LINEA MAGICA QUE FALTABA
    st.title("Sistema Comercial y POS")

    # Menú interno del módulo comercial
    menu = st.tabs(["🛒 Punto de Venta", "📜 Historial", "📦 Inventario y Almacenes"])

    # --- PESTAÑA 1: POS ---
    with menu[0]:
        st.header("Nueva Venta / POS")
        
        # Inicializar carrito en sesión
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Selección de Cliente
            client = st.text_input("Cliente", value="Cliente General")
            doc_type = st.radio("Documento", ["Nota Venta", "Boleta", "Factura"], horizontal=True)
            
            st.divider()
            
            # BUSCADOR DE PRODUCTOS
            st.subheader("🔍 Buscar Producto")
            search_term = st.text_input("Escribe nombre o código", placeholder="Ej: Bebedero...")
            
            # Consulta segura a la base de datos
            query = """
            SELECT p.id, p.name, p.unit_price, IFNULL(i.quantity, 0) as stock 
            FROM products p 
            LEFT JOIN inventory i ON p.id = i.product_id 
            WHERE p.name LIKE ? OR p.sku LIKE ?
            LIMIT 5
            """
            products = get_data(query, ('%' + search_term + '%', '%' + search_term + '%'))

            if not products.empty and search_term:
                for index, row in products.iterrows():
                    with st.expander(f"{row['name']} - S/. {row['unit_price']} (Stock: {row['stock']})"):
                        col_a, col_b = st.columns(2)
                        qty = col_a.number_input("Cant.", min_value=1, max_value=int(row['stock']) if row['stock'] > 0 else 1, key=f"q_{row['id']}")
                        if col_b.button("Añadir", key=f"add_{row['id']}"):
                            item = {
                                "id": row['id'],
                                "name": row['name'],
                                "price": row['unit_price'],
                                "qty": qty,
                                "total": row['unit_price'] * qty
                            }
                            st.session_state.cart.append(item)
                            st.success(f"Añadido: {row['name']}")
                            st.rerun()

        # --- CARRITO DE COMPRAS (DERECHA) ---
        with col2:
            st.subheader("🛒 Carrito")
            if len(st.session_state.cart) > 0:
                total_sale = 0
                for i, item in enumerate(st.session_state.cart):
                    st.write(f"**{item['qty']}x {item['name']}**")
                    st.write(f"S/. {item['total']:.2f}")
                    total_sale += item['total']
                    if st.button("🗑️", key=f"del_{i}"):
                        st.session_state.cart.pop(i)
                        st.rerun()
                    st.divider()
                
                st.metric("TOTAL A PAGAR", f"S/. {total_sale:.2f}")
                
                if st.button("✅ FINALIZAR VENTA", use_container_width=True, type="primary"):
                    # Guardar venta en BD
                    items_json = json.dumps(st.session_state.cart)
                    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    sql = "INSERT INTO quotes (customer_name, date, total_amount, items_json, status) VALUES (?, ?, ?, ?, ?)"
                    run_query(sql, (client, date_now, total_sale, items_json, 'VENDIDO'))
                    
                    # Restar stock (bucle)
                    for item in st.session_state.cart:
                        # OJO: Aquí simplificamos asumiendo almacén ID 1. 
                        # En el futuro se puede mejorar para detectar almacén.
                        sql_update = "UPDATE inventory SET quantity = quantity - ? WHERE product_id = ? AND warehouse_id = 1"
                        run_query(sql_update, (item['qty'], item['id']))
                    
                    st.session_state.cart = []
                    st.balloons()
                    st.success("¡Venta registrada correctamente!")
                    st.rerun()
            else:
                st.info("El carrito está vacío.")

    # --- PESTAÑA 2: HISTORIAL ---
    with menu[1]:
        st.header("Historial de Ventas")
        sales = get_data("SELECT id, date, customer_name, total_amount FROM quotes ORDER BY id DESC")
        st.dataframe(sales, use_container_width=True)

    # --- PESTAÑA 3: INVENTARIO ---
    with menu[2]:
        st.header("Gestión de Inventario")
        
        inv_tabs = st.tabs(["Stock y Productos", "Traslados", "Gestión de Datos"])
        
        # TABLA STOCK
        with inv_tabs[0]:
            # Consulta corregida que incluye Costo
            query_stock = """
            SELECT p.sku as SKU, p.name as Producto, 
            IFNULL(i.quantity, 0) as Stock, 
            p.unit_price as Precio_Unit, 
            p.price_dozen as P_Docena, 
            p.price_hundred as P_Ciento,
            p.import_cost as Costo
            FROM products p 
            LEFT JOIN inventory i ON p.id = i.product_id AND i.warehouse_id = 1
            ORDER BY p.id DESC
            """
            df_stock = get_data(query_stock)
            st.dataframe(df_stock, use_container_width=True)

        # CARGA MASIVA
        with inv_tabs[2]:
            st.write("### Carga Masiva desde Excel")
            uploaded_file = st.file_uploader("Sube tu Excel", type=['xlsx'])
            
            if uploaded_file:
                df_upload = pd.read_excel(uploaded_file)
                st.write("Vista previa:", df_upload.head())
                
                # Mapeo de columnas
                col_name = st.selectbox("Nombre", df_upload.columns)
                col_stock = st.selectbox("Stock", df_upload.columns)
                col_price = st.selectbox("Precio Unit", df_upload.columns)
                col_sku = st.selectbox("Columna SKU/Código (Opcional)", ["(Ignorar)"] + list(df_upload.columns))
                col_cost = st.selectbox("Costo", ["(Vacío)"] + list(df_upload.columns))
                
                if st.button("🚀 PROCESAR"):
                    count = 0
                    for index, row in df_upload.iterrows():
                        if pd.isna(row[col_name]): continue
                        
                        name = str(row[col_name])
                        stock = int(row[col_stock]) if pd.notna(row[col_stock]) else 0
                        price = float(row[col_price]) if pd.notna(row[col_price]) else 0
                        
                        # Lógica del SKU
                        if col_sku != "(Ignorar)":
                            sku = str(row[col_sku])
                        else:
                            # Si ignoramos SKU, usamos el nombre como identificador único
                            sku = name 

                        # Costo
                        cost = 0.0
                        if col_cost != "(Vacío)" and pd.notna(row[col_cost]):
                            cost = float(row[col_cost])

                        # 1. Insertar Producto
                        # Usamos INSERT OR IGNORE para que no falle si ya existe
                        try:
                            run_query(f"INSERT OR IGNORE INTO products (sku, name, unit_price, import_cost) VALUES (?, ?, ?, ?)", 
                                      (sku, name, price, cost))
                            
                            # Obtener ID del producto recién insertado (o el que ya existía)
                            prod_data = get_data("SELECT id FROM products WHERE sku = ?", (sku,))
                            if not prod_data.empty:
                                prod_id = prod_data.iloc[0]['id']
                                
                                # 2. Insertar Inventario (Almacén 1 por defecto)
                                # Primero intentamos actualizar
                                run_query("INSERT OR IGNORE INTO inventory (product_id, warehouse_id, quantity) VALUES (?, 1, ?)", (prod_id, stock))
                                # Si ya existía, sumamos (opcional) o actualizamos
                                run_query("UPDATE inventory SET quantity = ? WHERE product_id = ? AND warehouse_id = 1", (stock, prod_id))
                                
                                count += 1
                        except:
                            pass
                            
                    st.success(f"Cargados {count} productos.")
                    st.rerun()

            st.divider()
            if st.button("🧨 BORRAR TODO Y REINICIAR"):
                run_query("DELETE FROM inventory")
                run_query("DELETE FROM products")
                run_query("DELETE FROM quotes")
                run_query("DELETE FROM kardex")
                st.warning("Sistema reiniciado a cero.")
                st.rerun()
