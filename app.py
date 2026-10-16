import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Comparador Remito vs Factura", layout="wide")

st.title("📋 Comparador Remito vs Factura (PDF)")
st.write("Subí los archivos PDF de tu Remito y Factura para realizar la conciliación automática de ítems y cantidades.")

# --- Funciones de Extracción ---

def extraer_texto_pdf(file):
    """Extrae todo el texto plano de un archivo PDF subido."""
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
            texto += "\n"
    return texto

def procesar_lineas_pdf(texto):
    """
    Parsea las líneas del PDF buscando patrones de código/descripción, cantidad y precio.
    Ajusta estas expresiones regulares si tus PDFs tienen un formato muy específico.
    """
    items = []
    lineas = texto.split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
            
        # Busca números flotantes/enteros al final o dentro de la línea
        # Ejemplo de formato típico: "PROD-001 Producto de prueba 10 1500.00"
        coincidencias = re.findall(r'(\d+[\.,]?\d*)', linea)
        
        # Si la línea contiene al menos una cantidad
        if coincidencias:
            # Estrategia general de captura básica de items:
            partes = linea.split()
            # Intenta identificar descripciones e importes
            # Esta lógica se adapta según el proveedor/layout de comprobantes
            items.append({
                "linea_completa": linea,
                "valores_detectados": coincidencias
            })
            
    return lineas

# --- Interfaz de usuario ---

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Cargar Remito")
    pdf_remito = st.file_uploader("Subir PDF del Remito", type=["pdf"], key="remito")

with col2:
    st.subheader("2. Cargar Factura")
    pdf_factura = st.file_uploader("Subir PDF de la Factura", type=["pdf"], key="factura")

if pdf_remito and pdf_factura:
    st.divider()
    st.header("🔍 Resultado de la Comparación")
    
    texto_remito = extraer_texto_pdf(pdf_remito)
    texto_factura = extraer_texto_pdf(pdf_factura)
    
    # Extraer tablas directamente usando pdfplumber
    def extraer_tablas(file):
        filas = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # Limpiar celdas vacías o saltos de línea
                        row_limpia = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                        if any(row_limpia):
                            filas.append(row_limpia)
        return filas

    tablas_remito = extraer_tablas(pdf_remito)
    tablas_factura = extraer_tablas(pdf_factura)

    tab1, tab2, tab3 = st.tabs(["📊 Vista Comparativa", "📜 Texto Extraído Remito", "📜 Texto Extraído Factura"])

    with tab1:
        st.subheader("Tablas Detectadas en el Remito")
        if tablas_remito:
            df_remito = pd.DataFrame(tablas_remito)
            st.dataframe(df_remito, use_container_width=True)
        else:
            st.warning("No se detectaron tablas con formato estándar en el Remito. Revisá la solapa de texto plano.")

        st.subheader("Tablas Detectadas en la Factura")
        if tablas_factura:
            df_factura = pd.DataFrame(tablas_factura)
            st.dataframe(df_factura, use_container_width=True)
        else:
            st.warning("No se detectaron tablas con formato estándar en la Factura. Revisá la solapa de texto plano.")

        st.info("💡 **Tip:** Para hacer una comparación exacta por producto, podés mapear las columnas correspondientes a 'Código/Descripción' y 'Cantidad' de cada comprobante.")

    with tab2:
        st.text_area("Texto completo del Remito", texto_remito, height=300)

    with tab3:
        st.text_area("Texto completo de la Factura", texto_factura, height=300)

else:
    st.info("👆 Por favor, subí ambos archivos PDF arriba para iniciar el análisis.")