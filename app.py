import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from utils.db import init_db

# Page Config
st.set_page_config(
    page_title="Cressendo ERP",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize DB
init_db()

# CSS for styling
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; color: #2E7D32; font-weight: 700;}
    .sub-header {font-size: 1.5rem; color: #388E3C;}
    .card {background-color: #f8f9fa; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    .metric-value {font-size: 2rem; font-weight: bold; color: #1B5E20;}
</style>
""", unsafe_allow_html=True)

# --- CONFIG & PERSISTENCE ---
import os
import requests
from datetime import date

if not os.path.exists("documentos_sustento"):
    os.makedirs("documentos_sustento")

# --- AUTHENTICATION & SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.username = None
if 'quote_cart' not in st.session_state:
    st.session_state.quote_cart = []
if 'warehouses' not in st.session_state:
    # Fallback/Cache for warehouses
    st.session_state.warehouses = [{'name': 'Almacén Central', 'id': 1}] # Default
if 'products' not in st.session_state:
    st.session_state.products = pd.DataFrame()

if 'exchange_rate' not in st.session_state:
    st.session_state.exchange_rate = 3.75 # Default fallback

def get_sunat_rate():
    try:
        # Simplified public endpoint or just use a robust free one.
        # Using a reliable public JSON endpoint for demo or fallback to manual.
        # Note: apis.net.pe requires token in some endpoints. Inspecting user request for 'public API'.
        # Using local fallback if fails, but trying a generic request.
        response = requests.get("https://api.apis.net.pe/v1/tipo-cambio-sunat", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get('compra'), data.get('venta')
    except:
        pass
    return None, None

def login():
    st.markdown("<h2 style='text-align: center; color: #2E7D32;'>🔐 Cressendo ERP Login</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                from utils.db import get_data
                user = get_data("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
                if not user.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_role = user.iloc[0]['role']
                    st.session_state.username = user.iloc[0]['username']
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")

def logout():
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.username = None
    st.rerun()

# --- MAIN APP FLOW ---
if not st.session_state.logged_in:
    login()
else:
    # Sidebar Navigation
    with st.sidebar:
        # 1. Custom Logo Logic
        if os.path.exists("company_logo.png"):
             st.image("company_logo.png", width=150)
        else:
             st.image("https://cdn-icons-png.flaticon.com/512/3063/3063829.png", width=100) # Fallback
        
        st.title("Cressendo\nAgro-Tech")
        st.write(f"👤 **{st.session_state.username}** ({st.session_state.user_role})")
        
        # --- TIPO DE CAMBIO (SUNAT) ---
        st.divider()
        st.write("💱 **Tipo de Cambio (SUNAT)**")
        
        # Try fetch only once per session or on button click to avoid lag
        if 'tc_fetched' not in st.session_state:
             c, v = get_sunat_rate()
             if c and v:
                  st.session_state.exchange_rate = float(v) # Use Venta as standard for costs usually or let user pick
                  st.toast(f"TC Updated from SUNAT: {v}")
             st.session_state.tc_fetched = True

        tc_manual = st.number_input("T.C. Venta ($ -> S/.)", value=st.session_state.exchange_rate, step=0.001, format="%.3f")
        if tc_manual != st.session_state.exchange_rate:
             st.session_state.exchange_rate = tc_manual
             
        st.divider()

        # Define Menu based on Role
        if st.session_state.user_role == 'Admin':
            options = ["Home", "Commercial & POS", "Import Logistics", "HR & Payroll", "Accounting", "User Management", "Settings"]
            icons = ["house", "cart", "truck", "people", "file-earmark-text", "person-badge", "gear"]
        else:
            options = ["Home", "Commercial & POS"]
            icons = ["house", "cart"]
            
        selected = option_menu(
            menu_title="Menu",
            options=options,
            icons=icons,
            default_index=0,
            styles={
                "container": {"padding": "5px", "background-color": "#fafafa"},
                "icon": {"color": "green", "font-size": "25px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
                "nav-link-selected": {"background-color": "#4CAF50"},
            }
        )

        if st.button("Logout", icon="🚪"):
            logout()
            
        # --- INTERNAL CHAT (AVISOS DE GERENCIA) ---
        st.divider()
        with st.expander("📢 Avisos de Gerencia", expanded=True):
            from utils.db import run_query, get_data
            
            # Post Message (Admin Only)
            if st.session_state.user_role == 'Admin':
                with st.form("new_msg"):
                    txt = st.text_input("Nuevo Aviso")
                    urgent = st.checkbox("Urgente")
                    if st.form_submit_button("Publicar"):
                        run_query("INSERT INTO messages (username, message, is_urgent, date) VALUES (?, ?, ?, date('now'))", 
                                  (st.session_state.username, txt, urgent))
                        st.rerun()

            # View Messages (Last 5)
            # Create table if not exists check done in db init, but just in case
            try:
                msgs = get_data("SELECT * FROM messages ORDER BY id DESC LIMIT 5")
                if not msgs.empty:
                    for _, m in msgs.iterrows():
                        icon = "🚨" if m['is_urgent'] else "ℹ️"
                        st.markdown(f"{icon} **{m['username']}**: {m['message']}")
                        st.caption(f"{m['date']}")
                else:
                    st.info("No hay avisos.")
            except:
                st.info("Chat system initializing...")

    # Routing
    if selected == "Home":
        st.title(f"Welcome, {st.session_state.username}!")
        st.info("Select a module from the sidebar.")
        
        # Quick Dashboard
        c1, c2 = st.columns(2)
        c1.metric("Exchange Rate", f"S/. {st.session_state.exchange_rate}")
        
    elif selected == "Commercial & POS":
        try:
            from modules import commercial
            commercial.render()
        except ImportError:
            st.info("Commercial Module not yet implemented.")
            
    elif selected == "Import Logistics":
        if st.session_state.user_role != 'Admin':
            st.error("🚫 Access Denied")
        else:
            try:
                from modules import logistics
                logistics.render()
            except ImportError:
                st.info("Logistics Module not yet implemented.")

    elif selected == "HR & Payroll":
        if st.session_state.user_role != 'Admin':
            st.error("🚫 Access Denied")
        else:
            try:
                from modules import hr
                hr.render()
            except ImportError:
                st.info("HR Module not yet implemented.")
            
    elif selected == "Accounting":
        if st.session_state.user_role != 'Admin':
            st.error("🚫 Access Denied")
        else:
            try:
                from modules import accounting
                accounting.render()
            except ImportError:
                st.info("Accounting Module not yet implemented.")
                
    elif selected == "User Management":
        st.title("User Management")
        with st.form("new_user"):
            new_user = st.text_input("New Username")
            new_pass = st.text_input("New Password", type="password")
            new_role = st.selectbox("Role", ["Admin", "Vendedor"])
            if st.form_submit_button("Create User"):
                 from utils.db import run_query
                 try:
                     run_query("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_user, new_pass, new_role))
                     st.success(f"User {new_user} created!")
                 except:
                     st.error("User already exists.")
                     
    elif selected == "Settings":
        st.title("⚙️ System Settings")
        st.subheader("Branding & Customization")
        
        if st.session_state.user_role == 'Admin':
            upl_logo = st.file_uploader("Upload Company Logo (PNG/JPG)", type=['png', 'jpg', 'jpeg'])
            if upl_logo:
                with open("company_logo.png", "wb") as f:
                    f.write(upl_logo.getbuffer())
                st.success("Logo Updated! It will appear on the sidebar.")
                st.image("company_logo.png", width=200)
        else:
            st.error("Access Restricted")
