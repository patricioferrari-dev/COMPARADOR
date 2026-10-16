import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Remito vs Factura", page_icon="🧾", layout="wide")

st.title("🧾 Comparador de Remitos vs. Facturas (PDF)")
st.write("Sube los archivos PDF para analizar y comparar los datos, incluso en comprobantes digitales de ARCA/AFIP o sin bordes de tabla.")

# --- Funciones de Extracción Avanzada ---

def extraer_lineas_como_tabla(page):
    """
    Toma una página de PDF y procesa el texto estructurado por líneas.
    Ideal para comprobantes digitales que no tienen líneas de tabla dibujadas.
    """
    texto = page.extract_text(layout=True) or page.extract_text()
    if not texto:
        return []
    
    filas = []
    lineas = texto.split('\n')
    for linea in lineas:
        linea_limpia = linea.strip()
        if linea_limpia:
            # Dividir la línea cuando haya 2 o más espacios consecutivos (columnas implícitas)
            columnas = [col.strip() for col in re.split(r'\s{2,}', linea_limpia) if col.strip()]
            if columnas:
                filas.append(columnas)
    return filas

def procesar_paginas_pdf(pdf_file, paginas=None):
    """Extrae datos intentando primero por tablas físicas y luego por diseño de texto."""
    tablas_fisiscas = []
    filas_texto = []
    texto_bruto = ""
    
    with pdfplumber.open(pdf_file) as pdf:
        total_paginas = len(pdf.pages)
        
        if not paginas:
            paginas = list(range(1, total_paginas + 1))
            
        for num_pag in paginas:
            if 1 <= num_pag <= total_paginas:
                page = pdf.pages[num_pag - 1]
                
                # 1. Texto plano completo
                t = page.extract_text()
                if t:
                    texto_bruto += f"--- Página {num_pag} ---\n" + t + "\n\n"
                
                # 2. Tablas explícitas
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_limpia = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                        if any(row_limpia):
                            tablas_fisiscas.append(row_limpia)
                            
                # 3. Extracción de respaldo por alineación espacial
                filas_estructuradas = extraer_lineas_como_tabla(page)
                if filas_estructuradas:
                    filas_texto.extend(filas_estructuradas)
                    
    # Retorna las tablas explícitas o, en su defecto, las líneas estructuradas de texto
    resultado_tabla = tablas_fisiscas if tablas_fisiscas else filas_texto
    return resultado_tabla, texto_bruto

# --- Selección de Modo de Carga ---

modo_carga = st.radio(
    "¿Cómo deseas subir los documentos?",
    ["Un solo PDF (Remito + Factura juntas)", "Dos PDFs separados"],
    horizontal=True
)

tablas_remito, tablas_factura = [], []
texto_remito, texto_factura = "", ""
listo = False

if modo_carga == "Un solo PDF (Remito + Factura juntas)":
    archivo_unico = st.file_uploader("Subir PDF unificado", type=["pdf"], key="unico")
    if archivo_unico:
        with pdfplumber.open(archivo_unico) as pdf:
            cant_pags = len(pdf.pages)
        
        col1, col2 = st.columns(2)
        with col1:
            pag_remito = st.multiselect("Página(s) del Remito:", options=list(range(1, cant_pags + 1)), default=[1] if cant_pags >= 1 else [])
        with col2:
            pag_factura = st.multiselect("Página(s) de la Factura:", options=list(range(1, cant_pags + 1)), default=[2] if cant_pags >= 2 else [1])
            
        if pag_remito and pag_factura:
            tablas_remito, texto_remito = procesar_paginas_pdf(archivo_unico, pag_remito)
            tablas_factura, texto_factura = procesar_paginas_pdf(archivo_unico, pag_factura)
            listo = True
else:
    c1, c2 = st.columns(2)
    with c1:
        pdf_remito = st.file_uploader("Subir PDF del Remito", type=["pdf"], key="remito")
    with c2:
        pdf_factura = st.file_uploader("Subir PDF de la Factura", type=["pdf"], key="factura")
        
    if pdf_remito and pdf_factura:
        tablas_remito, texto_remito = procesar_paginas_pdf(pdf_remito)
        tablas_factura, texto_factura = procesar_paginas_pdf(pdf_factura)
        listo = True

# --- Despliegue de Resultados ---

if listo:
    st.divider()
    st.header("🔍 Resultados del Análisis")

    tab1, tab2, tab3 = st.tabs(["📊 Estructura Detectada", "📄 Texto Plano Remito", "📄 Texto Plano Factura"])

    with tab1:
        col_r, col_f = st.columns(2)
        
        with col_r:
            st.subheader("📋 Remito")
            if tablas_remito:
                st.dataframe(pd.DataFrame(tablas_remito), use_container_width=True)
            else:
                st.error("No se detectó texto ni tablas. Si es una imagen o escaneo de baja calidad, prueba subir un PDF digital.")

        with col_f:
            st.subheader("🧾 Factura")
            if tablas_factura:
                st.dataframe(pd.DataFrame(tablas_factura), use_container_width=True)
            else:
                st.error("No se detectó texto ni tablas en la factura.")

    with tab2:
        st.text_area("Texto extraído del Remito", texto_remito, height=400)

    with tab3:
        st.text_area("Texto extraído de la Factura", texto_factura, height=400)
