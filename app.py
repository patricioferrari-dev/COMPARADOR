import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Remito vs Factura", layout="wide")

st.title("📋 Comparador Remito vs Factura (PDF)")
st.write("Podés subir **dos archivos separados** o **un solo PDF** (con las páginas de ambos documentos) para realizar la extracción y comparación.")

# --- Función de Extracción Avanzada ---

def extraer_datos_documento(pdf_file, paginas=None):
    """
    Extrae texto y tablas de páginas específicas utilizando estrategias de alineación 
    de texto (ideal para comprobantes de ARCA/AFIP y órdenes de compra sin bordes).
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
                
                # 1. Extraer texto preservando disposición de columnas
                t = page.extract_text(layout=True) or page.extract_text() or ""
                texto_completo += f"--- Página {num_pag} ---\n" + t + "\n\n"

                # 2. Estrategia basada en alineación de texto para tablas sin líneas/bordes
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
                            # Filtrar filas vacías o de una sola celda
                            if any(row_limpia) and len([c for c in row_limpia if c]) > 1:
                                filas_detectadas.append(row_limpia)

                # 3. Fallback: Parseo por regex si no se estructuraron celdas
                if not filas_detectadas and t:
                    lines = t.split('\n')
                    for line in lines:
                        match = re.search(r'([A-Z0-9_-]{3,})\s+(.+?)\s+(\d+[\.,]?\d*)\s+(\d+[\.,]?\d*)', line)
                        if match:
                            filas_detectadas.append(list(match.groups()))

    return filas_detectadas, texto_completo


# --- Selección del Modo de Carga ---

modo_carga = st.radio(
    "¿Cómo querés subir los documentos?",
    ["Un solo PDF (Remito + Factura en el mismo archivo)", "Dos PDFs separados"],
    horizontal=True
)

tablas_remito, tablas_factura = [], []
texto_remito, texto_factura = "", ""
listo_para_comparar = False

if modo_carga == "Un solo PDF (Remito + Factura en el mismo archivo)":
    archivo_unico = st.file_uploader("Subir el PDF unificado", type=["pdf"], key="unico")
    
    if archivo_unico:
        with pdfplumber.open(archivo_unico) as pdf:
            cant_paginas = len(pdf.pages)
        
        st.info(f"📄 El archivo subido tiene **{cant_paginas} página(s)**.")
        
        col1, col2 = st.columns(2)
        with col1:
            pag_remito = st.multiselect(
                "Seleccioná la(s) página(s) del Remito / Orden:",
                options=list(range(1, cant_paginas + 1)),
                default=[1] if cant_paginas >= 1 else []
            )
        with col2:
            pag_factura = st.multiselect(
                "Seleccioná la(s) página(s) de la Factura:",
                options=list(range(1, cant_paginas + 1)),
                default=[2] if cant_paginas >= 2 else [1]
            )
            
        if pag_remito and pag_factura:
            tablas_remito, texto_remito = extraer_datos_documento(archivo_unico, pag_remito)
            tablas_factura, texto_factura = extraer_datos_documento(archivo_unico, pag_factura)
            listo_para_comparar = True
        else:
            st.warning("Seleccioná al menos una página para el remito y una para la factura.")

else:
    col1, col2 = st.columns(2)
    with col1:
        pdf_remito = st.file_uploader("Subir PDF del Remito / Orden de Compra", type=["pdf"], key="remito")
    with col2:
        pdf_factura = st.file_uploader("Subir PDF de la Factura", type=["pdf"], key="factura")
        
    if pdf_remito and pdf_factura:
        tablas_remito, texto_remito = extraer_datos_documento(pdf_remito)
        tablas_factura, texto_factura = extraer_datos_documento(pdf_factura)
        listo_para_comparar = True


# --- Mostrar Resultados ---

if listo_para_comparar:
    st.divider()
    st.header("🔍 Resultado de la Extracción y Comparación")

    tab1, tab2, tab3 = st.tabs(["📊 Tablas Estructuradas", "📜 Texto Remito / Orden", "📜 Texto Factura"])

    with tab1:
        col_r, col_f = st.columns(2)
        
        with col_r:
            st.subheader("📋 Remito / Orden de Compra")
            if tablas_remito:
                st.dataframe(pd.DataFrame(tablas_remito), use_container_width=True)
            else:
                st.warning("No se detectaron tablas automáticas. Revisá la pestaña de texto plano.")

        with col_f:
            st.subheader("🧾 Factura")
            if tablas_factura:
                st.dataframe(pd.DataFrame(tablas_factura), use_container_width=True)
            else:
                st.warning("No se detectaron tablas automáticas. Revisá la pestaña de texto plano.")

    with tab2:
        st.text_area("Texto detectado en Remito / Orden", texto_remito, height=350)

    with tab3:
        st.text_area("Texto detectado en Factura", texto_factura, height=350)
