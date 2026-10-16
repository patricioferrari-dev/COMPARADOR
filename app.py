import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="Comparador Remito vs Factura", layout="wide")

st.title("📋 Comparador Remito vs Factura (PDF)")
st.write("Podés subir **dos archivos separados** o **un solo PDF** que contenga tanto el remito como la factura.")

# --- Funciones de Extracción ---

def extraer_tablas_y_texto(pdf_file, paginas=None):
    """Extrae tablas y texto de páginas específicas de un PDF."""
    filas_tablas = []
    texto_completo = ""
    
    with pdfplumber.open(pdf_file) as pdf:
        total_paginas = len(pdf.pages)
        
        # Si no se especifican páginas, procesa todas
        if not paginas:
            paginas = list(range(1, total_paginas + 1))
            
        for num_pag in paginas:
            if 1 <= num_pag <= total_paginas:
                page = pdf.pages[num_pag - 1]
                
                # Extraer texto
                t = page.extract_text()
                if t:
                    texto_completo += f"--- Página {num_pag} ---\n" + t + "\n\n"
                
                # Extraer tablas
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_limpia = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                        if any(row_limpia):
                            filas_tablas.append(row_limpia)
                            
    return filas_tablas, texto_completo

# --- Selección de Modo de Carga ---

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
                "Seleccioná la(s) página(s) del Remito:",
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
            tablas_remito, texto_remito = extraer_tablas_y_texto(archivo_unico, pag_remito)
            tablas_factura, texto_factura = extraer_tablas_y_texto(archivo_unico, pag_factura)
            listo_para_comparar = True
        else:
            st.warning("Seleccioná al menos una página para el remito y una para la factura.")

else:
    col1, col2 = st.columns(2)
    with col1:
        pdf_remito = st.file_uploader("Subir PDF del Remito", type=["pdf"], key="remito")
    with col2:
        pdf_factura = st.file_uploader("Subir PDF de la Factura", type=["pdf"], key="factura")
        
    if pdf_remito and pdf_factura:
        tablas_remito, texto_remito = extraer_tablas_y_texto(pdf_remito)
        tablas_factura, texto_factura = extraer_tablas_y_texto(pdf_factura)
        listo_para_comparar = True

# --- Mostrar Resultados ---

if listo_para_comparar:
    st.divider()
    st.header("🔍 Resultado de la Comparación")

    tab1, tab2, tab3 = st.tabs(["📊 Vista Comparativa", "📜 Texto Extraído Remito", "📜 Texto Extraído Factura"])

    with tab1:
        col_r, col_f = st.columns(2)
        
        with col_r:
            st.subheader("📋 Datos del Remito")
            if tablas_remito:
                st.dataframe(pd.DataFrame(tablas_remito), use_container_width=True)
            else:
                st.warning("No se detectaron tablas automáticas en las páginas del remito.")

        with col_f:
            st.subheader("🧾 Datos de la Factura")
            if tablas_factura:
                st.dataframe(pd.DataFrame(tablas_factura), use_container_width=True)
            else:
                st.warning("No se detectaron tablas automáticas en las páginas de la factura.")

    with tab2:
        st.text_area("Texto detectado en el Remito", texto_remito, height=350)

    with tab3:
        st.text_area("Texto detectado en la Factura", texto_factura, height=350)
