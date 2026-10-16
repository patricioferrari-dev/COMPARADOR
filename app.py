import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Comprobantes PDF", layout="wide")

st.title("📋 Comparador de Documentos (Orden / Remito / Factura)")

def extraer_datos_documento(pdf_file, paginas=None):
    """
    Extrae tablas ajustando tolerancias de pdfplumber y usa fallback 
    de Expresiones Regulares si no detecta estructura de celdas.
    """
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

                # 1. Estrategia con tolerancias avanzadas para tablas sin bordes visibles
                table_settings = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 5,
                    "join_tolerance": 5,
                    "min_words_vertical": 2
                }
                
                tables = page.extract_tables(table_settings)
                
                if tables:
                    for table in tables:
                        for row in table:
                            row_limpia = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                            if any(row_limpia) and len([c for c in row_limpia if c]) > 1:
                                filas_detectadas.append(row_limpia)

                # 2. Fallback de Extracción por Regex si no encontró filas
                if not filas_detectadas and t:
                    lines = t.split('\n')
                    for line in lines:
                        # Busca patrones típicos de ítems: [Código] [Descripción] [Cantidad] [Precio/Total]
                        match = re.search(r'([A-Z0-9_-]{3,})\s+(.+?)\s+(\d+[\.,]?\d*)\s+(\d+[\.,]?\d*)', line)
                        if match:
                            filas_detectadas.append(list(match.groups()))

    return filas_detectadas, texto_completo


# --- Interfaz de Carga ---
st.subheader("Subí tus archivos PDF para analizar")

col1, col2 = st.columns(2)
with col1:
    file_doc1 = st.file_uploader("Documento 1 (Ej. Orden de Compra / Remito)", type=["pdf"], key="doc1")
with col2:
    file_doc2 = st.file_uploader("Documento 2 (Ej. Factura)", type=["pdf"], key="doc2")

if file_doc1 and file_doc2:
    st.divider()
    
    filas_1, texto_1 = extraer_datos_documento(file_doc1)
    filas_2, texto_2 = extraer_datos_documento(file_doc2)

    tab1, tab2, tab3 = st.tabs(["📊 Comparación Estructurada", "📜 Texto Doc 1", "📜 Texto Doc 2"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Documento 1")
            if filas_1:
                df1 = pd.DataFrame(filas_1)
                st.dataframe(df1, use_container_width=True)
            else:
                st.warning("No se estructuraron celdas. Revisá la pestaña de texto plano.")

        with c2:
            st.subheader("Documento 2")
            if filas_2:
                df2 = pd.DataFrame(filas_2)
                st.dataframe(df2, use_container_width=True)
            else:
                st.warning("No se estructuraron celdas. Revisá la pestaña de texto plano.")

    with tab2:
        st.text_area("Texto plano de Doc 1", texto_1, height=400)

    with tab3:
        st.text_area("Texto plano de Doc 2", texto_2, height=400)
