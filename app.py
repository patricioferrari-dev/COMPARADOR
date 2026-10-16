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
        linea_limpia = linea.strip().replace('|', ' ')
        if not linea_limpia:
            continue
            
        # Buscar directamente los códigos de MyFamily (MF...) o Chapitas (CH...)
        if re.search(r'\b(MF[A-Z0-9]+|CH\d{2,})\b', linea_limpia):
            # Limpiar espacios múltiples para separar las columnas
            columnas = [col.strip() for col in re.split(r'\s{2,}|\t', linea_limpia) if col.strip()]
            
            # Si el separador de espacios falla, partimos por espacios simples
            if len(columnas) < 3:
                columnas = linea_limpia.split()
                
            filas.append(columnas)
            continue
            
        # Respaldo para filas de Factura que empiezan con "Cantidad,00" (Ej: "2,00 CH01...")
        match_fac = re.match(r'^(\d+,\d{2})\s+([A-Z0-9_-]+)\s+(.+)$', linea_limpia)
        if match_fac:
            filas.append(list(match_fac.groups()))

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
                st.dataframe(pd.DataFrame(tablas_remito))
            else:
                st.warning("No se detectaron códigos.")
        with col_f:
            st.subheader("🧾 Factura")
            if tablas_factura:
                st.dataframe(pd.DataFrame(tablas_factura))
            else:
                st.warning("No se detectaron códigos.")

    with tab2:
        st.text_area("Texto interpretado Orden", texto_remito, height=400)
    with tab3:
        st.text_area("Texto interpretado Factura", texto_factura, height=400)
