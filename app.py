import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Remito vs Factura", layout="wide")

st.title("📋 Comparador Inteligente de Comprobantes")
st.write("Cargá tus archivos PDF para extraer automáticamente las listas de ítems, cantidades y precios.")

# --- Motor de Extracción Específico para Comprobantes ARCA / VANDEL ---

def procesar_texto_a_filas(texto):
    """
    Analiza el texto línea por línea buscando patrones exactos de artículos comerciales.
    Ignora encabezados, datos fiscales y totales.
    """
    filas = []
    lineas = texto.split('\n')
    
    for linea in lineas:
        linea_limpia = linea.strip().replace('|', '') # Limpia separadores fantasma
        if not linea_limpia:
            continue
            
        # Ignorar líneas de totales o impuestos
        if re.search(r'(Subtotal|Total|Impuestos|IVA|CUIT|Condición|Página|Fecha|Base Imponnible|Son \$|CAE N|Neto Gravado)', linea_limpia, re.IGNORECASE):
            continue

        # ESTRATEGIA 1: Separación por múltiples espacios (Layout visual)
        # Identifica columnas cuando el PDF las separa con espacios largos
        columnas = [col.strip() for col in re.split(r'\s{2,}', linea_limpia) if col.strip()]
        if len(columnas) >= 4:
            # Verifica que al menos dos columnas sean numéricas (ej. Cantidad y Precio)
            num_count = sum(1 for c in columnas if re.search(r'\d', c))
            if num_count >= 2:
                filas.append(columnas)
                continue

        # ESTRATEGIA 2: Regex específico para Facturas (Ej: "2,00 CH01 DAISY 21,00 20.527,273 41.054,55")
        match_factura = re.match(r'^(\d+[\.,]\d{2})\s+([A-Z0-9_-]+)\s+(.+?)\s+(\d+[\.,]\d{2})\s+([\d\.,]+)\s+([\d\.,]+)$', linea_limpia)
        if match_factura:
            filas.append(list(match_factura.groups()))
            continue

        # ESTRATEGIA 3: Regex específico para Órdenes de Compra (Ej: "01 252069 MFXL01 Chapita... 2 12.371,24 5,00 12.371,24")
        match_oc = re.match(r'^(\d{2})\s+(\d+)\s+([A-Z0-9_-]+)\s+(.+?)\s+(\d+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)$', linea_limpia)
        if match_oc:
            filas.append(list(match_oc.groups()))
            continue

        # ESTRATEGIA 4: Fallback genérico para líneas con al menos 1 palabra y 2 números
        tokens = linea_limpia.split()
        if len(tokens) >= 4:
            numeros = [t for t in tokens if re.search(r'\d+[\.,]?\d*', t)]
            palabras = [t for t in tokens if re.search(r'[A-Za-z]', t)]
            if len(numeros) >= 2 and len(palabras) >= 1:
                filas.append(tokens)

    return filas

def extraer_datos_documento(pdf_file, paginas=None):
    """
    Combina la lectura de disposición visual (layout=True) con el procesador de texto.
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
                
                # Extraer conservando la alineación original de las columnas
                t = page.extract_text(layout=True) or page.extract_text() or ""
                texto_completo += f"--- Página {num_pag} ---\n" + t + "\n\n"

                # Procesar el texto extraído
                if t:
                    filas_pagina = procesar_texto_a_filas(t)
                    if filas_pagina:
                        filas_detectadas.extend(filas_pagina)

    return filas_detectadas, texto_completo


# --- Interfaz de Carga ---

modo_carga = st.radio(
    "¿Cómo querés subir los documentos?",
    ["Un solo PDF (Remito/Orden + Factura en el mismo archivo)", "Dos PDFs separados"],
    horizontal=True
)

tablas_remito, tablas_factura = [], []
texto_remito, texto_factura = "", ""
listo_para_comparar = False

if modo_carga == "Un solo PDF (Remito/Orden + Factura en el mismo archivo)":
    archivo_unico = st.file_uploader("Subir el PDF unificado", type=["pdf"], key="unico")
    
    if archivo_unico:
        with pdfplumber.open(archivo_unico) as pdf:
            cant_paginas = len(pdf.pages)
        
        st.info(f"📄 El archivo tiene **{cant_paginas} página(s)**.")
        
        col1, col2 = st.columns(2)
        with col1:
            pag_remito = st.multiselect("Página(s) Remito / Orden de Compra:", list(range(1, cant_paginas + 1)), default=[1] if cant_paginas >= 1 else [])
        with col2:
            pag_factura = st.multiselect("Página(s) Factura:", list(range(1, cant_paginas + 1)), default=[2] if cant_paginas >= 2 else [1])
            
        if pag_remito and pag_factura:
            tablas_remito, texto_remito = extraer_datos_documento(archivo_unico, pag_remito)
            tablas_factura, texto_factura = extraer_datos_documento(archivo_unico, pag_factura)
            listo_para_comparar = True

else:
    col1, col2 = st.columns(2)
    with col1:
        pdf_remito = st.file_uploader("Subir Remito / Orden de Compra", type=["pdf"], key="remito")
    with col2:
        pdf_factura = st.file_uploader("Subir Factura", type=["pdf"], key="factura")
        
    if pdf_remito and pdf_factura:
        tablas_remito, texto_remito = extraer_datos_documento(pdf_remito)
        tablas_factura, texto_factura = extraer_datos_documento(pdf_factura)
        listo_para_comparar = True


# --- Presentación de Resultados ---

if listo_para_comparar:
    st.divider()
    st.header("🔍 Datos Extraídos Automáticamente")

    tab1, tab2, tab3 = st.tabs(["📊 Tabla de Ítems Extraídos", "📜 Texto Orden/Remito", "📜 Texto Factura"])

    with tab1:
        col_r, col_f = st.columns(2)
        
        with col_r:
            st.subheader("📋 Orden de Compra / Remito")
            if tablas_remito:
                st.dataframe(pd.DataFrame(tablas_remito), use_container_width=True)
            else:
                st.warning("No se detectaron ítems numéricos en las líneas.")

        with col_f:
            st.subheader("🧾 Factura")
            if tablas_factura:
                st.dataframe(pd.DataFrame(tablas_factura), use_container_width=True)
            else:
                st.warning("No se detectaron ítems numéricos en las líneas.")

    with tab2:
        st.text_area("Texto interpretado de la Orden", texto_remito, height=400)

    with tab3:
        st.text_area("Texto interpretado de la Factura", texto_factura, height=400)
