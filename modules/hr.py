import streamlit as st
import pandas as pd
from datetime import datetime
from utils.db import run_query, get_data

def render():
    st.title("Recursos Humanos y Nómina")
    
    tab1, tab2 = st.tabs(["👥 Empleados", "💰 Nómina (Pagos)"])
    
    with tab1:
        st.subheader("Gestión de Empleados")
        with st.expander("Nuevo Empleado"):
            with st.form("new_emp"):
                name = st.text_input("Nombre Completo")
                role = st.selectbox("Cargo", ["Vendedor", "Almacenero", "Administrador", "Contador"])
                salary = st.number_input("Salario Base (S/.)", min_value=0.0)
                if st.form_submit_button("Guardar"):
                    run_query("INSERT INTO employees (name, role, salary, date_joined) VALUES (?, ?, ?, date('now'))", (name, role, salary))
                    st.success("Empleado guardado")
                    st.rerun()
        
        # Lista
        emps = get_data("SELECT * FROM employees")
        st.dataframe(emps, use_container_width=True)

    with tab2:
        st.subheader("Procesar Pagos")
        
        # Formulario de Pago
        with st.form("pay_run"):
            emp_opts = get_data("SELECT id, name FROM employees")
            if not emp_opts.empty:
                e_map = {r['name']: r['id'] for _, r in emp_opts.iterrows()}
                sel_e = st.selectbox("Empleado", list(e_map.keys()))
                period = st.date_input("Periodo").strftime("%Y-%m")
                bonus = st.number_input("Bonos", min_value=0.0)
                deduc = st.number_input("Deducciones", min_value=0.0)
                
                if st.form_submit_button("Generar Pago"):
                    eid = e_map[sel_e]
                    base = get_data(f"SELECT salary FROM employees WHERE id={eid}").iloc[0]['salary']
                    net = base + bonus - deduc
                    run_query("INSERT INTO payroll (employee_id, period, base_salary, bonuses, deductions, net_pay, processed_date) VALUES (?, ?, ?, ?, ?, ?, date('now'))",
                              (eid, period, base, bonus, deduc, net))
                    st.success("Pago registrado")
                    st.rerun()
            else:
                st.warning("Registra empleados primero.")
        
        st.divider()
        st.write("### Historial de Pagos")
        # CORRECCIÓN AQUÍ: Usamos e.name en lugar de e.full_name
        history = get_data("""
            SELECT p.id, p.period, e.name as Empleado, p.net_pay as Neto, p.processed_date 
            FROM payroll p 
            JOIN employees e ON p.employee_id = e.id 
            ORDER BY p.id DESC
        """)
        st.dataframe(history, use_container_width=True)