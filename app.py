import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Remito vs Factura", layout="wide")
st.title("📋 Comparador Inteligente de Comprobantes")

def procesar_texto_a_filas(texto):
    filas = []
    lineas = texto.split('\n')
    
    for linea in lineas:
        # Limpiamos barras y caracteres raros
        l = linea.replace('|', ' ').strip()
        if not l:
            continue
            
        # Filtramos subtotales y encabezados para que no los sume como productos
        if re.search(r'(Subtotal|Total|Impuestos|IVA|CUIT|Condición|Página|Fecha|Base|Bruto)', l, re.IGNORECASE):
            continue

        # BUSCADOR UNIVERSAL: Captura la fila si tiene palabras y al menos un número decimal (ej. 12,00 o 1.234,56)
        if re.search(r'\d+,\d{2}', l) and re.search(r'[A-Za-z]', l):
            # Intentamos separar por tabulaciones o espacios grandes
            columnas = [col.strip() for col in re.split(r'\s{2,}|\t', l) if col.strip()]
            
            # Si todo quedó pegado, lo separamos por espacios simples
            if len(columnas) < 3:
                columnas = l.split()
                
            filas.append(columnas)

    return filas

def extraer_datos_documento(pdf_file, paginas=None):
    filas_detectadas = []
    texto_completo = ""

    with pdfplumber.open(pdf_file) as pdf:
        total_paginas = len(pdf.pages)
        if not paginas:
            paginas = list(range(1, total_paginas + 1))

        for num_pag in paginas:
            if 1 <= num_pag <= total_paginas:
                page = pdf.pages[num_pag - 1]
                # Extraemos el texto crudo intentando mantener la posición visual
                t = page.extract_text(layout=True) or page.extract_text() or ""
                texto_completo += f"--- Página {num_pag} ---\n" + t + "\n\n"

                if t:
                    filas_pagina = procesar_texto_a_filas(t)
                    if filas_pagina:
                        filas_detectadas.extend(filas_pagina)

    return filas_detectadas, texto_completo

# --- Interfaz de Carga ---
modo_carga = st.radio("¿Cómo querés subir los documentos?", ["Un solo PDF (Remito/Orden + Factura)", "Dos PDFs separados"], horizontal=True)

tablas_remito, tablas_factura = [], []
texto_remito, texto_factura = "", ""
listo_para_comparar = False

if modo_carga == "Un solo PDF (Remito/Orden + Factura)":
    archivo_unico = st.file_uploader("Subir el PDF unificado", type=["pdf"], key="unico")
    if archivo_unico:
        with pdfplumber.open(archivo_unico) as pdf:
            cant_paginas = len(pdf.pages)
        col1, col2 = st.columns(2)
        with col1:
            pag_remito = st.multiselect("Página(s) Remito / Orden:", list(range(1, cant_paginas + 1)), default=[1] if cant_paginas >= 1 else [])
        with col2:
            pag_factura = st.multiselect("Página(s) Factura:", list(range(1, cant_paginas + 1)), default=[2] if cant_paginas >= 2 else [1])
            
        if pag_remito and pag_factura:
            tablas_remito, texto_remito = extraer_datos_documento(archivo_unico, pag_remito)
            tablas_factura, texto_factura = extraer_datos_documento(archivo_unico, pag_factura)
            listo_para_comparar = True
else:
    col1, col2 = st.columns(2)
    with col1:
        pdf_remito = st.file_uploader("Subir Remito / Orden", type=["pdf"], key="remito")
    with col2:
        pdf_factura = st.file_uploader("Subir Factura", type=["pdf"], key="factura")
        
    if pdf_remito and pdf_factura:
        tablas_remito, texto_remito = extraer_datos_documento(pdf_remito)
        tablas_factura, texto_factura = extraer_datos_documento(pdf_factura)
        listo_para_comparar = True

# --- Resultados ---
if listo_para_comparar:
    st.divider()
    st.header("🔍 Datos Extraídos")
    tab1, tab2, tab3 = st.tabs(["📊 Tabla de Ítems", "📜 Texto Orden", "📜 Texto Factura"])

    with tab1:
        col_r, col_f = st.columns(2)
        with col_r:
            st.subheader("📋 Orden de Compra")
            if tablas_remito:
                st.dataframe(pd.DataFrame(tablas_remito), use_container_width=True)
            else:
                st.warning("Aún no se detectan artículos.")
        with col_f:
            st.subheader("🧾 Factura")
            if tablas_factura:
                st.dataframe(pd.DataFrame(tablas_factura), use_container_width=True)
            else:
                st.warning("Aún no se detectan artículos.")

    with tab2:
        st.text_area("Texto interpretado Orden", texto_remito, height=400)
    with tab3:
        st.text_area("Texto interpretado Factura", texto_factura, height=400)
