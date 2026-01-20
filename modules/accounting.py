import streamlit as st
import pandas as pd
import os
from datetime import datetime
from utils.db import run_query, get_data

def render():
    st.title("📑 Accounting & Taxation")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["Registro de Ventas (PLE)", "Registro de Compras", "Kardex / Inventario"])

    # --- TAB 1: REGISTRO DE VENTAS (PLE) ---
    with tab1:
        st.subheader("Registro de Ventas e Ingresos (Format 14.1 PLE)")
        
        # Date Filter
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", value=datetime.now().replace(day=1))
        end_date = col2.date_input("End Date", value=datetime.now())
        
        # 1. Total Cash Flow (Includes 'Nota de Venta')
        all_sales = get_data(f"SELECT total_amount FROM sales WHERE date BETWEEN '{start_date}' AND '{end_date}'")
        total_cash = all_sales['total_amount'].sum() if not all_sales.empty else 0.0
        
        # 2. Taxable Sales (Factura/Boleta only)
        sales = get_data(f"SELECT * FROM sales WHERE date BETWEEN '{start_date}' AND '{end_date}' AND doc_type IN ('Factura', 'Boleta')")
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Flujo de Caja (Total)", f"S/. {total_cash:,.2f}", help="Incluye Notas de Venta + Comprobantes")
        
        if not sales.empty:
            # Calc Tax
            sales['Base Imponible'] = sales['total_amount'] / 1.18
            sales['IGV'] = sales['total_amount'] - sales['Base Imponible']
            
            total_taxable = sales['total_amount'].sum()
            total_igv = sales['IGV'].sum()
            renta = sales['Base Imponible'].sum() * 0.01 # 1% MYPE
            
            m2.metric("Ventas Declaradas (Sunat)", f"S/. {total_taxable:,.2f}")
            m3.metric("IGV Generado (Débito)", f"S/. {total_igv:,.2f}")
            st.caption(f"📉 Impuesto a la Renta Estimado (1.5% aprox): S/. {sales['Base Imponible'].sum() * 0.015:,.2f}")

            # Create Display DataFrame for PLE
            ple_df = pd.DataFrame({
                "Fecha": sales['date'],
                "Tipo": sales['doc_type'],
                "Serie": "F001/B001",
                "Número": sales['id'].astype(str).str.zfill(8),
                "Cliente": sales['customer_name'],
                "Base Imponible": sales['Base Imponible'],
                "IGV": sales['IGV'],
                "Importe Total": sales['total_amount']
            })
            
            st.dataframe(ple_df.style.format({
                "Base Imponible": "{:.2f}",
                "IGV": "{:.2f}",
                "Importe Total": "{:.2f}"
            }), use_container_width=True)
            
            # Export
            csv = ple_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar PLE (CSV)", data=csv, file_name="ventas_ple_tax_only.csv", mime="text/csv")
            
        else:
            st.info("No Taxable Sales (Factura/Boleta) in this period.")
            m2.metric("Ventas Declaradas", "S/. 0.00")
            m3.metric("IGV Generado", "S/. 0.00")

    # --- TAB 2: REGISTRO DE COMPRAS ---
    with tab2:
        st.subheader("Registro de Compras (Expenses)")
        
        with st.expander("📝 Registrar Nueva Compra (Factura)", expanded=False):
            with st.form("new_purchase"):
                c1, c2, c3 = st.columns(3)
                date_inv = c1.date_input("Fecha Emisión")
                provider = c2.text_input("Proveedor")
                ruc_prov = c3.text_input("RUC Proveedor")
                
                c4, c5, c6 = st.columns(3)
                doc_type = c4.selectbox("Tipo Doc", ["Factura", "Boleta", "DAM", "Recibo Honorarios"])
                series = c5.text_input("Serie")
                number = c6.text_input("Número")
                
                c7, c8 = st.columns(2)
                base = c7.number_input("Base Imponible", min_value=0.0, step=0.01)
                igv = c8.number_input("IGV (18%)", value=base*0.18, step=0.01)
                
                # File Upload
                uploaded_file = st.file_uploader("Sustento (PDF/Img)", type=['pdf', 'png', 'jpg'])
                
                if st.form_submit_button("Registrar Compra"):
                    total = base + igv
                    
                    # File Persistence Logic
                    file_path = ""
                    if uploaded_file:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{timestamp}_{provider}_{doc_type}.pdf".replace(" ", "_")
                        file_path = os.path.join("documentos_sustento", safe_name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                    
                    try:
                        run_query("""INSERT INTO purchase_invoices 
                            (date, provider, ruc, doc_type, series, number, base_amount, igv_amount, total_amount, file_path)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                            (date_inv, provider, ruc_prov, doc_type, series, number, base, igv, total, file_path))
                        
                        st.success("Compra Registrada!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving purchase: {e}")

        st.divider()
        purchases = get_data("SELECT * FROM purchase_invoices ORDER BY date DESC")
        st.dataframe(purchases)
        
        # Show file links (local workaround)
        if not purchases.empty:
            st.write("### Submitted Documents")
            for _, row in purchases.iterrows():
                if row['file_path']:
                    st.write(f"📄 **{row['provider']} ({row['doc_type']})**: `{row['file_path']}`")

    # --- TAB 3: KARDEX ---
    with tab3:
        st.subheader("Control de Inventarios (Kardex)")
        
        k_tab1, k_tab2 = st.tabs(["💎 Valorizado (Actual)", "📜 Historial de Movimientos"])
        
        with k_tab1:
            kardex = get_data("""
                SELECT 
                    p.sku, 
                    p.name AS producto, 
                    w.name AS almacen, 
                    i.quantity AS stock, 
                    p.unit_price AS precio_venta, 
                    p.import_cost AS costo_unitario 
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                JOIN warehouses w ON i.warehouse_id = w.id
            """)
            
            if not kardex.empty:
                kardex['Costo Total'] = kardex['stock'] * kardex['costo_unitario']
                kardex['Valor Venta Total'] = kardex['stock'] * kardex['precio_venta']
                
                st.dataframe(kardex.style.format({
                    "precio_venta": "S/. {:.2f}",
                    "costo_unitario": "$ {:.2f}",
                    "Costo Total": "$ {:.2f}",
                    "Valor Venta Total": "S/. {:.2f}"
                }), use_container_width=True)
                
                total_inv_val = kardex['Costo Total'].sum()
                st.metric("Valor Total Inventario (Costo)", f"$ {total_inv_val:,.2f}")
            else:
                st.info("Inventory is empty.")

        with k_tab2:
            st.markdown("### 🕵️ Audit Trail (Movimientos)")
            kardex_hist = get_data("""
                SELECT 
                    k.date, 
                    k.timestamp,
                    p.name as producto, 
                    w.name as almacen, 
                    k.movement_type, 
                    k.reason, 
                    k.quantity
                FROM kardex k
                JOIN products p ON k.product_id = p.id
                JOIN warehouses w ON k.warehouse_id = w.id
                ORDER BY k.id DESC
            """)
            
            if not kardex_hist.empty:
                st.dataframe(kardex_hist, use_container_width=True)
            else:
                st.info("No movements recorded yet.")
