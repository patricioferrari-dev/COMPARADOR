import streamlit as st
import pdfplumber
import pandas as pd
import google.generativeai as genai
import json

st.set_page_config(page_title="Comparador IA: Remito vs Factura", layout="wide")

st.title("🤖 Comparador Automático con Inteligencia Artificial")
st.write("Usa IA para leer PDFs desordenados, extraer los artículos y compararlos automáticamente.")

# --- Configuración de la API ---
with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Ingresá tu API Key de Gemini:", type="password")
    st.markdown("[Obtener API Key gratis aquí](https://aistudio.google.com/app/apikey)")

if api_key:
    genai.configure(api_key=api_key)
    modelo = genai.GenerativeModel('gemini-1.5-flash')

def extraer_texto_pdf(pdf_file, paginas):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for num in paginas:
            if 1 <= num <= len(pdf.pages):
                page = pdf.pages[num - 1]
                texto += page.extract_text(layout=True) or page.extract_text() or ""
                texto += "\n"
    return texto

def extraer_datos_con_ia(texto, tipo_doc):
    if not texto.strip():
        st.warning(f"No pudimos leer el texto de {tipo_doc}. Verificá que no sea una imagen escaneada vacía.")
        return pd.DataFrame()

    prompt = f"""
    Analizá el siguiente texto de un comprobante ({tipo_doc}).
    Extraé todos los artículos y devolvé un arreglo JSON con las siguientes claves: "codigo", "descripcion", "cantidad", "precio".
    Si falta un dato, usá un string vacío "" o 0.0 para números. No incluyas impuestos ni totales.
    
    Texto:
    {texto}
    """
    
    try:
        # Modo estricto: Obliga a Gemini a devolver solo datos válidos, sin texto conversacional
        respuesta = modelo.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        datos = json.loads(respuesta.text)
        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"Error procesando el {tipo_doc}.")
        st.info("Detalle técnico para el desarrollador: " + str(e))
        return pd.DataFrame()

# --- Interfaz de Carga ---
if not api_key:
    st.warning("👈 Por favor, ingresá tu API Key en el panel izquierdo para comenzar.")
else:
    modo_carga = st.radio("Formato de subida:", ["Un solo PDF (Remito + Factura)", "Dos PDFs separados"], horizontal=True)

    df_remito = pd.DataFrame()
    df_factura = pd.DataFrame()
    listo_para_comparar = False

    if modo_carga == "Un solo PDF (Remito + Factura)":
        archivo_unico = st.file_uploader("Subir PDF", type=["pdf"])
        if archivo_unico:
            with pdfplumber.open(archivo_unico) as pdf:
                cant = len(pdf.pages)
            c1, c2 = st.columns(2)
            with c1: pag_remito = st.multiselect("Páginas Remito/Orden:", list(range(1, cant + 1)), default=[1])
            with c2: pag_factura = st.multiselect("Páginas Factura:", list(range(1, cant + 1)), default=[2] if cant > 1 else [1])
            
            if st.button("🚀 Extraer y Comparar"):
                with st.spinner("La IA está leyendo los documentos..."):
                    texto_remito = extraer_texto_pdf(archivo_unico, pag_remito)
                    texto_factura = extraer_texto_pdf(archivo_unico, pag_factura)
                    df_remito = extraer_datos_con_ia(texto_remito, "Orden de Compra / Remito")
                    df_factura = extraer_datos_con_ia(texto_factura, "Factura")
                    listo_para_comparar = True

    else:
        c1, c2 = st.columns(2)
        with c1: pdf_remito = st.file_uploader("Subir Remito/Orden", type=["pdf"])
        with c2: pdf_factura = st.file_uploader("Subir Factura", type=["pdf"])
        
        if pdf_remito and pdf_factura:
            if st.button("🚀 Extraer y Comparar"):
                with st.spinner("La IA está leyendo los documentos..."):
                    texto_remito = extraer_texto_pdf(pdf_remito, [1]) 
                    texto_factura = extraer_texto_pdf(pdf_factura, [1])
                    df_remito = extraer_datos_con_ia(texto_remito, "Orden de Compra / Remito")
                    df_factura = extraer_datos_con_ia(texto_factura, "Factura")
                    listo_para_comparar = True

    # --- Resultados y Cruce ---
    if listo_para_comparar and not df_remito.empty and not df_factura.empty:
        st.divider()
        st.header("✅ Extracción Exitosa")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📋 Datos Orden/Remito")
            st.dataframe(df_remito, use_container_width=True)
        with c2:
            st.subheader("🧾 Datos Factura")
            st.dataframe(df_factura, use_container_width=True)

        st.divider()
        st.header("⚖️ Conciliación Automática")
        
        if 'codigo' in df_remito.columns and 'codigo' in df_factura.columns:
            df_cruce = pd.merge(df_remito, df_factura, on='codigo', how='outer', suffixes=('_remito', '_factura'))
            
            # Aseguramos que la columna de cantidad se calcule bien aunque haya faltantes
            df_cruce['diferencia_cant'] = pd.to_numeric(df_cruce['cantidad_remito'], errors='coerce').fillna(0) - pd.to_numeric(df_cruce['cantidad_factura'], errors='coerce').fillna(0)
            
            st.write("Comparamos los artículos basándonos en su código. Las filas con diferencias de cantidad están resaltadas en rojo.")
            
            def resaltar_diferencias(row):
                if row['diferencia_cant'] != 0:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
                
            st.dataframe(df_cruce.style.apply(resaltar_diferencias, axis=1), use_container_width=True)
        else:
            st.warning("No se detectó una columna de código clara para hacer el cruce.")
