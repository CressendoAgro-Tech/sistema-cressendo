import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from utils.db import init_db, get_data

# --- IMPORTAR TUS MÓDULOS ---
# (Esto conecta las carpetas que ya subiste)
import modules.commercial as commercial
import modules.logistics as logistics
import modules.hr as hr
import modules.accounting as accounting

# Configuración de la página
st.set_page_config(page_title="Cressendo ERP", layout="wide", page_icon="🌐")

# Estilos CSS para ocultar marcas de agua
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Inicializar Base de Datos
init_db()

# --- GESTIÓN DE SESIÓN (LOGIN) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

def login():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 Cressendo ERP Login")
        try:
            st.image("company_logo.png", width=200)
        except:
            pass
            
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", use_container_width=True):
            # Verificar usuario
            user = get_data("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            
            if not user.empty:
                st.session_state.logged_in = True
                st.session_state.username = user.iloc[0]['username']
                st.session_state.user_role = user.iloc[0]['role']
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.rerun()

# --- APP PRINCIPAL ---
if not st.session_state.logged_in:
    login()
else:
    # BARRA LATERAL (MENU COMPLETO)
    with st.sidebar:
        try:
            st.image("company_logo.png", width=150)
        except:
            st.write("## Cressendo")
            
        st.write(f"👤 **{st.session_state.username}**")
        st.divider()
        
        # AQUÍ ESTÁN TODAS LAS OPCIONES
        selected = option_menu(
            menu_title="Panel Principal",
            options=[
                "Home", 
                "Comercial & POS", 
                "Logística e Import", 
                "Recursos Humanos", 
                "Contabilidad", 
                "Cerrar Sesión"
            ],
            icons=["house", "cart", "globe", "people", "cash", "box-arrow-left"],
            menu_icon="cast",
            default_index=0,
        )

    # NAVEGACIÓN
    if selected == "Cerrar Sesión":
        logout()
        
    elif selected == "Home":
        st.title(f"Bienvenido al Sistema, {st.session_state.username}")
        st.info("Selecciona un módulo a la izquierda para comenzar a trabajar.")
        
        # Un pequeño resumen visual (Dashboard rápido)
        col1, col2, col3 = st.columns(3)
        col1.metric("Dólar Hoy", "S/. 3.366")
        col2.metric("Estado del Sistema", "En Línea 🟢")
        col3.metric("Usuario", st.session_state.username)

    elif selected == "Comercial & POS":
        commercial.app()
        
    elif selected == "Logística e Import":
        logistics.app()
        
    elif selected == "Recursos Humanos":
        hr.app()
        
    elif selected == "Contabilidad":
        accounting.app()
