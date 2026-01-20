import streamlit as st
import pandas as pd
import os
from utils.db import run_query, get_data

def render():
    st.title("🚢 Logistics & Import Management")

    tab1, tab2 = st.tabs(["New Import & Costing", "Manage Documents"])

    with tab1:
        render_new_import()

    with tab2:
        render_docs()

def render_new_import():
    st.subheader("1. Register Import Data (Costs)")
    
    with st.expander("Step 1: Create Import Headers", expanded=True):
        col1, col2, col3 = st.columns(3)
        dam = col1.text_input("DAM / Customs Num")
        arr_date = col2.date_input("Arrival Date")
        status = col3.selectbox("Status", ["Draft", "In Transit", "Nationalized"])
        
        c1, c2, c3 = st.columns(3)
        freight = c1.number_input("Total Freight ($)", min_value=0.0)
        insurance = c2.number_input("Total Insurance ($)", min_value=0.0)
        ad_valorem_rate = c3.selectbox("Ad Valorem Rate", [0.0, 0.06, 0.11], format_func=lambda x: f"{x*100}%")
        
        exc_rate = st.number_input("Exchange Rate (PEN/$)", value=3.75, step=0.01)

        if st.button("Create/Update Import Header"):
            # Check if exists (simplified update logic would go here, for now insert)
            run_query("""INSERT INTO imports 
                (dam_number, arrival_date, freight, insurance, ad_valorem_rate, exchange_rate, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                (dam, str(arr_date), freight, insurance, ad_valorem_rate, exc_rate, status))
            st.success(f"Import {dam} created!")
            st.rerun()

    st.subheader("2. Add Items & Calculate Costs")
    
    # Select Active Import
    imports = get_data("SELECT * FROM imports WHERE status != 'Nationalized' ORDER BY id DESC")
    if imports.empty:
        st.info("No active imports found.")
        return

    imp_opts = {f"{row['dam_number']} ({row['status']})": row['id'] for _, row in imports.iterrows()}
    sel_imp = st.selectbox("Select Import to Manage", options=list(imp_opts.keys()))
    imp_id = imp_opts[sel_imp]
    
    # Get current import data for calcs
    curr_imp = imports[imports['id'] == imp_id].iloc[0]
    
    # --- BULK STOCK UPLOAD (XLSX) ---
    with st.expander("📦 Procesar Stock Masivo (Excel)", expanded=False):
        st.info("Sube un Excel con: SKU, Cantidad, CostoUnitario (FOB)")
        upl_stock = st.file_uploader("Stock Excel", type=['xlsx'])
        
        if upl_stock:
            if st.button("Procesar Ingreso de Stock"):
                try:
                    df_stock = pd.read_excel(upl_stock)
                    # Expected cols: SKU, Quantity, FOB
                    count = 0
                    for _, row in df_stock.iterrows():
                        sku = str(row.get('SKU', ''))
                        qty = int(row.get('Cantidad', 0))
                        fob = float(row.get('CostoUnitario', 0))
                        name = str(row.get('Nombre', 'Imported Product')) # Optional
                        
                        if sku:
                            # 1. Add to Import Items
                            run_query("INSERT INTO import_items (import_id, product_name, quantity, fob_unit) VALUES (?, ?, ?, ?)",
                                      (imp_id, f"{name} ({sku})", qty, fob))
                            count += 1
                            
                    st.success(f"Added {count} items to Import #{curr_imp['dam_number']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing Excel: {e}")

    # Add Item Form (Manual)
    with st.form("add_imp_item"):
        c1, c2, c3 = st.columns(3)
        p_name = c1.text_input("Product Name/Desc")
        qty = c2.number_input("Quantity", min_value=1)
        fob_u = c3.number_input("Unit FOB ($)", min_value=0.01)
        
        if st.form_submit_button("Add Item"):
            run_query("INSERT INTO import_items (import_id, product_name, quantity, fob_unit) VALUES (?, ?, ?, ?)",
                      (imp_id, p_name, qty, fob_u))
            st.success("Item added.")
            st.rerun()

    # Calculation Table
    st.markdown("### Cost Distribution (Prorrateo)")
    items = get_data(f"SELECT * FROM import_items WHERE import_id = {imp_id}")
    
    if not items.empty:
        # PANDAS LOGIC FOR PRORATING
        items['Total FOB'] = items['quantity'] * items['fob_unit']
        total_fob_import = items['Total FOB'].sum()
        
        if total_fob_import > 0:
            # Distribution Factors
            items['Factor'] = items['Total FOB'] / total_fob_import
            
            # Distribute Costs
            total_freight = curr_imp['freight']
            total_insurance = curr_imp['insurance']
            
            items['Allocated Freight'] = items['Factor'] * total_freight
            items['Allocated Insurance'] = items['Factor'] * total_insurance
            
            # Duties
            items['Ad Valorem'] = items['Total FOB'] * curr_imp['ad_valorem_rate']
            
            # CIF
            items['CIF Cost'] = items['Total FOB'] + items['Allocated Freight'] + items['Allocated Insurance']
            
            # Real Unit Cost (Dollars)
            items['Unit Cost $'] = (items['CIF Cost'] + items['Ad Valorem']) / items['quantity']
            
            # Real Unit Cost (Soles)
            items['Unit Cost S/.'] = items['Unit Cost $'] * curr_imp['exchange_rate']

            # Display
            st.dataframe(items[['product_name', 'quantity', 'fob_unit', 'Allocated Freight', 'Allocated Insurance', 'Unit Cost $', 'Unit Cost S/.']].style.format("{:.2f}", subset=['fob_unit', 'Allocated Freight', 'Allocated Insurance', 'Unit Cost $', 'Unit Cost S/.']))
            
            st.info("💡 The 'Unit Cost' includes FOB + Prorated Freight/Insurance + Ad Valorem.")
            
            # Perceptions Calculator
            st.divider()
            cif_total = items['CIF Cost'].sum()
            ad_val_total = items['Ad Valorem'].sum()
            igv_base = cif_total + ad_val_total
            igv = igv_base * 0.18
            total_import_cost = igv_base + igv
            
            st.write(f"**Total CIF:** ${cif_total:,.2f} | **Total Ad Valorem:** ${ad_val_total:,.2f} | **IGV (18%):** ${igv:,.2f}")
            
            perc_rate = st.radio("Perception Rate", [0.035, 0.10, 0.05], captions=["3.5% (Frequent)", "10% (First Import)", "5% (Used/Other)"], horizontal=True)
            perception_amt = total_import_cost * perc_rate
            st.success(f"💰 Perception to Pay: ${perception_amt:,.2f} (S/. {perception_amt * curr_imp['exchange_rate']:,.2f})")

        else:
            st.warning("Total FOB is 0. Check item prices.")
    else:
        st.info("Add items to calculate costs.")

def render_docs():
    st.subheader("Document Management (Persistent)")
    
    # Multiple File Upload
    uploaded_files = st.file_uploader("Upload Docs (DAM, Invoice, Packing List)", type=['pdf', 'jpg', 'png', 'xlsx'], accept_multiple_files=True)
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Persistent Path
            safe_name = uploaded_file.name.replace(" ", "_")
            save_path = os.path.join("documentos_sustento", safe_name)
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.toast(f"Saved: {safe_name}")
            
    st.divider()
    st.write("### 📂 Archivos en 'documentos_sustento'")
    
    if os.path.exists("documentos_sustento"):
        files = os.listdir("documentos_sustento")
        if files:
            for f in files:
                col1, col2 = st.columns([4, 1])
                col1.write(f"📄 {f}")
                # In a real deployed app, serving files requires specific config.
                # Here we just list them to confirm persistence.
        else:
            st.info("No documents found.")
