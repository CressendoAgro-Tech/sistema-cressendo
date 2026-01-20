import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from utils.db import run_query, get_data, init_db

def render():
    try:
        st.title("Sistema Comercial y POS")

        # --- AUTO-REPARACIÓN ---
        if 'offline_mode' not in st.session_state:
            st.session_state.offline_mode = False
        if 'quote_cart' not in st.session_state:
            st.session_state.quote_cart = []
        
        # Asegurar almacén ID 1
        try:
            res = get_data("SELECT count(*) as c FROM warehouses")
            if res.empty or res.iloc[0]['c'] == 0:
                run_query("INSERT INTO warehouses (id, name, location) VALUES (1, 'Almacén Central', 'Principal')")
        except:
            init_db()

        tab1, tab2, tab3 = st.tabs(["🛒 Punto de Venta", "📄 Historial", "📦 Inventario y Almacenes"])

        with tab1:
            render_pos()
        with tab2:
            render_quotes()
        with tab3:
            render_inventory()

    except Exception as e:
        st.error(f"⚠️ Error de sistema: {str(e)}")

# ==========================================
# 🛒 POS
# ==========================================
def render_pos():
    st.subheader("Nueva Venta / POS")
    
    with st.container():
        c1, c2 = st.columns([2, 1])
        cliente = c1.text_input("Cliente", value="Cliente General")
        doc_type = c2.radio("Documento", ["Nota Venta", "Boleta", "Factura"], horizontal=True)
        
    st.divider()

    col_prod, col_cart = st.columns([1, 1])
    
    with col_prod:
        st.markdown("##### 🔍 Buscar Producto")
        # Mostramos SKU en el buscador para facilitar
        query_prods = """
            SELECT p.id, p.sku, p.name, p.unit_price, p.price_dozen, p.price_hundred, IFNULL(i.quantity, 0) as stock 
            FROM products p 
            LEFT JOIN inventory i ON p.id = i.product_id AND i.warehouse_id = 1
        """
        prods_df = get_data(query_prods)
        
        if not prods_df.empty:
            # Formato: "INC-01 | Incubadora (Stock: 5)"
            prods_df['display'] = prods_df.apply(lambda x: f"{x['sku']} | {x['name']} (Stock: {int(x['stock'])})", axis=1)
            prod_map = dict(zip(prods_df['display'], prods_df['id']))
            
            sel_label = st.selectbox("Seleccione producto:", options=list(prod_map.keys()))
            
            if sel_label:
                pid = prod_map[sel_label]
                p_data = prods_df[prods_df['id'] == pid].iloc[0]
                
                qty = st.number_input("Cantidad:", min_value=1, value=1, max_value=int(p_data['stock']) if p_data['stock'] > 0 else 9999)
                
                # Lógica de precios automática
                precio_final = p_data['unit_price']
                tipo_precio = "Unitario"
                
                if qty >= 100 and p_data['price_hundred'] > 0:
                    precio_final = p_data['price_hundred']
                    tipo_precio = "Mayorista (Ciento)"
                elif qty >= 12 and p_data['price_dozen'] > 0:
                    precio_final = p_data['price_dozen']
                    tipo_precio = "Mayorista (Docena)"
                
                st.info(f"💰 Precio: **S/. {precio_final:.2f}** ({tipo_precio})")
                
                if st.button("➕ Agregar", type="primary"):
                    item = {
                        "id": int(pid),
                        "name": p_data['name'],
                        "sku": p_data['sku'],
                        "price": float(precio_final),
                        "qty": int(qty),
                        "subtotal": float(precio_final * qty),
                        "type": tipo_precio
                    }
                    st.session_state.quote_cart.append(item)
                    st.toast("Producto agregado")

    with col_cart:
        st.markdown("##### 🛒 Carrito")
        if len(st.session_state.quote_cart) > 0:
            cart_df = pd.DataFrame(st.session_state.quote_cart)
            st.dataframe(cart_df[['qty', 'name', 'price', 'subtotal']], use_container_width=True)
            
            total = cart_df['subtotal'].sum()
            st.metric("TOTAL A PAGAR", f"S/. {total:.2f}")
            
            b1, b2 = st.columns(2)
            if b1.button("🗑️ Vaciar"):
                st.session_state.quote_cart = []
                st.rerun()
            
            if b2.button("✅ FINALIZAR", type="primary"):
                items_json = json.dumps(st.session_state.quote_cart)
                full_customer = f"{cliente}|TYPE:{doc_type}"
                
                run_query("INSERT INTO quotes (customer_name, date, total_amount, items_json, status) VALUES (?, date('now'), ?, ?, 'Invoiced')", 
                          (full_customer, total, items_json))
                
                for item in st.session_state.quote_cart:
                    run_query(f"UPDATE inventory SET quantity = quantity - {item['qty']} WHERE product_id = {item['id']} AND warehouse_id = 1")
                    run_query("INSERT INTO kardex (date, product_id, warehouse_id, movement_type, reason, quantity) VALUES (date('now'), ?, 1, 'SALIDA', ?, ?)",
                              (item['id'], f"Venta {doc_type}", item['qty']))

                st.session_state.quote_cart = []
                st.balloons()
                st.success("¡Venta Exitosa!")
                time.sleep(2)
                st.rerun()

# ==========================================
# 📄 HISTORIAL
# ==========================================
def render_quotes():
    st.subheader("Historial de Ventas")
    df_sales = get_data("SELECT id, date, customer_name, total_amount, status FROM quotes ORDER BY id DESC LIMIT 20")
    if not df_sales.empty:
        df_sales['Cliente'] = df_sales['customer_name'].apply(lambda x: x.split('|')[0] if '|' in x else x)
        df_sales['Doc'] = df_sales['customer_name'].apply(lambda x: x.split('TYPE:')[1] if 'TYPE:' in x else 'Nota')
        st.dataframe(df_sales[['id', 'date', 'Cliente', 'Doc', 'total_amount']], use_container_width=True)
    else:
        st.info("Sin ventas registradas.")

# ==========================================
# 📦 INVENTARIO (CON EDITOR DE SKU)
# ==========================================
def render_inventory():
    st.subheader("Gestión de Inventario")
    inv_tab1, inv_tab2, inv_tab3 = st.tabs(["Stock y Productos", "Traslados", "Gestión de Datos"])
    
    with inv_tab1:
        if st.button("🔄 Actualizar Tabla"):
            st.rerun()

        query = """
            SELECT 
                p.sku as SKU, 
                p.name as Producto, 
                IFNULL(i.quantity, 0) as Stock, 
                p.unit_price as Precio_Unit,
                p.price_dozen as P_Docena,
                p.price_hundred as P_Ciento,
                p.import_cost as Costo
            FROM products p
            LEFT JOIN inventory i ON p.id = i.product_id AND i.warehouse_id = 1
            ORDER BY p.id DESC
        """
        df = get_data(query)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.caption(f"Productos: {len(df)}")
        else:
            st.info("Inventario vacío.")

    with inv_tab2:
        st.info("Módulo de traslados.")

    with inv_tab3:
        st.markdown("### 🛠️ Herramientas")
        
        # === NUEVA HERRAMIENTA: EDITOR DE PRODUCTO ===
        with st.expander("✏️ EDITAR SKU / NOMBRE / PRECIOS (Manual)", expanded=False):
            st.info("Selecciona un producto para corregir su SKU o Precios.")
            prod_list = get_data("SELECT id, sku, name FROM products")
            
            if not prod_list.empty:
                # Mapa para el selector
                pmap = {f"{row['sku']} - {row['name']}": row['id'] for _, row in prod_list.iterrows()}
                sel_edit = st.selectbox("Selecciona Producto a Editar:", list(pmap.keys()))
                
                if sel_edit:
                    pid_edit = pmap[sel_edit]
                    # Traer datos actuales
                    curr = get_data(f"SELECT * FROM products WHERE id={pid_edit}").iloc[0]
                    
                    with st.form("edit_form"):
                        c1, c2 = st.columns(2)
                        new_sku = c1.text_input("SKU (Código)", value=curr['sku'])
                        new_name = c2.text_input("Nombre", value=curr['name'])
                        
                        c3, c4, c5 = st.columns(3)
                        new_price = c3.number_input("Precio Unit.", value=float(curr['unit_price']))
                        new_doz = c4.number_input("P. Docena", value=float(curr['price_dozen']))
                        new_hun = c5.number_input("P. Ciento", value=float(curr['price_hundred']))
                        
                        if st.form_submit_button("💾 GUARDAR CAMBIOS"):
                            run_query("""
                                UPDATE products SET sku=?, name=?, unit_price=?, price_dozen=?, price_hundred=?
                                WHERE id=?
                            """, (new_sku, new_name, new_price, new_doz, new_hun, pid_edit))
                            st.success(f"Producto actualizado: {new_sku}")
                            time.sleep(1)
                            st.rerun()

        st.divider()
        
        # CARGA MASIVA (INTACTA)
        with st.expander("📂 Carga Masiva (Excel)", expanded=False):
            uploaded_file = st.file_uploader("Subir Excel", type=['xlsx'], key="upl_final_v4")
            if uploaded_file:
                header_row = st.number_input("Fila de títulos", value=0)
                try:
                    df = pd.read_excel(uploaded_file, header=header_row)
                    cols = list(df.columns); cols.insert(0, "(Ignorar)")
                    
                    def find(keys):
                        for i, c in enumerate(cols):
                            for k in keys:
                                if k.upper() in str(c).upper(): return i
                        return 0

                    st.write("Asocia las columnas:")
                    c1, c2, c3 = st.columns(3)
                    col_name = c1.selectbox("Nombre", cols, index=find(['NOM', 'PROD']))
                    col_stock = c2.selectbox("Stock", cols, index=find(['STOCK', 'CANT']))
                    col_price = c3.selectbox("Precio Unit", cols, index=find(['PRECIO', 'UNIT']))
                    
                    c4, c5, c6 = st.columns(3)
                    col_cost = c4.selectbox("Costo", cols, index=find(['COST']))
                    col_doz = c5.selectbox("P. Docena", cols, index=find(['DOCENA', 'DOZ']))
                    col_hun = c6.selectbox("P. Ciento", cols, index=find(['CIENTO', 'HUN']))

                    # Opcion para elegir columna SKU del Excel si existe
                    col_sku_xls = st.selectbox("Columna SKU/Código (Opcional)", cols, index=find(['SKU', 'COD', 'REF']))
                    
                    if st.button("🚀 PROCESAR"):
                        if col_name == "(Ignorar)" or col_stock == "(Ignorar)":
                            st.error("Falta Nombre o Stock")
                        else:
                            count = 0
                            bar = st.progress(0)
                            for idx, row in df.iterrows():
                                try:
                                    name = str(row[col_name]).strip()
                                    
                                    def get_float(x):
                                        try: return float(str(x).replace('S/.','').replace(',','').strip())
                                        except: return 0.0
                                    
                                    price = get_float(row[col_price]) if col_price != "(Ignorar)" else 0.0
                                    cost = get_float(row[col_cost]) if col_cost != "(Ignorar)" else 0.0
                                    p_doz = get_float(row[col_doz]) if col_doz != "(Ignorar)" else 0.0
                                    p_hun = get_float(row[col_hun]) if col_hun != "(Ignorar)" else 0.0
                                    stock = int(get_float(row[col_stock])) if col_stock != "(Ignorar)" else 0
                                    
                                    # SI EL EXCEL TIENE SKU, USARLO. SI NO, GENERARLO.
                                    if col_sku_xls != "(Ignorar)":
                                        sku = str(row[col_sku_xls]).strip()
                                    else:
                                        sku = f"SKU-{int(time.time())}-{idx}"
                                    
                                    # Insert Product
                                    run_query("""
                                        INSERT INTO products (sku, name, category, unit_price, price_dozen, price_hundred, import_cost)
                                        VALUES (?, ?, 'Excel', ?, ?, ?, ?)
                                    """, (sku, name, price, p_doz, p_hun, cost))
                                    
                                    # Insert Inventory
                                    pid_df = get_data(f"SELECT id FROM products WHERE sku='{sku}'")
                                    if not pid_df.empty:
                                        pid = pid_df.iloc[0]['id']
                                        run_query(f"INSERT INTO inventory (product_id, warehouse_id, quantity) VALUES ({pid}, 1, {stock})")
                                    
                                    count += 1
                                    bar.progress(min(count/len(df), 1.0))
                                except: pass
                            st.success(f"Cargados {count} productos.")
                            time.sleep(1)
                            st.rerun()
                except: st.error("Error en archivo")

        st.divider()
        if st.button("🧨 BORRAR TODO Y REINICIAR"):
            run_query("DELETE FROM inventory"); run_query("DELETE FROM products"); run_query("DELETE FROM kardex")
            st.rerun()