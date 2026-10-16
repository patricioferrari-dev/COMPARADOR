import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Remito vs Factura", layout="wide")

st.title("📋 Comparador Remito vs Factura / Orden de Compra")
st.write("Cargá tus archivos PDF para extraer automáticamente las listas de ítems, cantidades y precios.")

# --- Procesador Inteligente de Filas / Ítems ---

def extraer_items_de_texto(texto):
    """
    Analiza el texto plano del PDF buscando renglones de artículos.
    Filtra encabezados, pies de página, datos fiscales o sellos.
    """
    filas = []
    lineas = texto.split('\n')
    
    for linea in lineas:
        linea_limpia = linea.strip()
        if not linea_limpia:
            continue
            
        # Ignorar líneas que sean claramente de encabezados o totales generales
        if re.search(r'(Subtotal|Total|Impuestos|IVA|CUIT|Condición|Página|Fecha)', linea_limpia, re.IGNORECASE):
            continue

        # Detectar patrones con números (cantidades y/o precios al final o entre medio)
        # Ejemplo: "01 252069 MFXL01 Chapita XL Bone Blue 2 12.371,24 5,00 12.371,24"
        partes = [p.strip() for p in re.split(r'\s{2,}', linea_limpia) if p.strip()]
        
        if len(partes) >= 2:
            filas.append(partes)
            
    return filas

def extraer_datos_documento(pdf_file, paginas=None):
    """
    Motor de extracción en 3 capas para leer comprobantes sin bordes de celdas.
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
                
                # Extracción preservando layout posicional
                t = page.extract_text(layout=True) or page.extract_text() or ""
                texto_completo += f"--- Página {num_pag} ---\n" + t + "\n\n"

                # Capa 1: Extraer usando detección visual por alineación de texto
                table_settings = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "min_words_vertical": 1
                }
                
                tables = page.extract_tables(table_settings)
                
                if tables:
                    for table in tables:
                        for row in table:
                            row_limpia = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                            # Guardar filas válidas que tengan más de un campo con datos
                            if any(row_limpia) and len([c for c in row_limpia if c]) >= 2:
                                filas_detectadas.append(row_limpia)

                # Capa 2: Fallback si Capa 1 no generó resultados
                if not filas_detectadas and t:
                    filas_fallback = extraer_items_de_texto(t)
                    if filas_fallback:
                        filas_detectadas.extend(filas_fallback)

    return filas_detectadas, texto_completo


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
                "Seleccioná la(s) página(s) del Remito / Orden de Compra:",
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
            st.warning("Seleccioná al menos una página para cada documento.")

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


# --- Presentación de Resultados ---

if listo_para_comparar:
    st.divider()
    st.header("🔍 Datos Extraídos para Comparación")

    tab1, tab2, tab3 = st.tabs(["📊 Vista de Ítems Detectados", "📜 Texto Remito / Orden", "📜 Texto Factura"])

    with tab1:
        col_r, col_f = st.columns(2)
        
        with col_r:
            st.subheader("📋 Remito / Orden de Compra")
            if tablas_remito:
                df_rem = pd.DataFrame(tablas_remito)
                st.dataframe(df_rem, use_container_width=True)
            else:
                st.warning("No se estructuraron filas automáticamente en el Remito. Podés revisar el texto plano en la segunda pestaña.")

        with col_f:
            st.subheader("🧾 Factura")
            if tablas_factura:
                df_fac = pd.DataFrame(tablas_factura)
                st.dataframe(df_fac, use_container_width=True)
            else:
                st.warning("No se estructuraron filas automáticamente en la Factura. Podés revisar el texto plano en la tercera pestaña.")

    with tab2:
        st.text_area("Texto plano detectado en Remito / Orden", texto_remito, height=350)

    with tab3:
        st.text_area("Texto plano detectado en Factura", texto_factura, height=350)
