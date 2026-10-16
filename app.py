import streamlit as st
import pdfplumber
import pandas as pd
import google.generativeai as genai
import json
import io

st.set_page_config(page_title="Comparador IA: Remito vs Factura", layout="wide")

st.title("🤖 Comparador Automático con Inteligencia Artificial")
st.write("Usa IA para leer PDFs desordenados, extraer los artículos y compararlos automáticamente.")

# --- Configuración de la API ---
with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Ingresá tu API Key de Gemini:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    modelo = genai.GenerativeModel('gemini-1.5-flash')

def extraer_texto_pdf(archivo_bytes, paginas):
    texto = ""
    with pdfplumber.open(io.BytesIO(archivo_bytes)) as pdf:
        for num in paginas:
            if 1 <= num <= len(pdf.pages):
                page = pdf.pages[num - 1]
                t = page.extract_text(layout=True) or page.extract_text() or ""
                texto += t + "\n"
    return texto

def extraer_datos_con_ia(texto, tipo_doc):
    if not texto.strip():
        st.warning(f"⚠️ El documento '{tipo_doc}' parece ser una imagen sin texto real. No se pudo leer.")
        return pd.DataFrame()

    prompt = f"""
    Analizá el siguiente texto de un comprobante ({tipo_doc}).
    Extraé todos los artículos y devolvé un arreglo JSON con las siguientes claves: "codigo", "descripcion", "cantidad", "precio".
    Si falta un dato, usá un string vacío "" o 0.0 para números. No incluyas impuestos ni totales.
    
    Texto:
    {texto}
    """
    
    try:
        respuesta = modelo.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        datos = json.loads(respuesta.text)
        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"❌ Error al pedirle a la IA que estructure los datos de {tipo_doc}.")
        return pd.DataFrame()

# --- Interfaz de Carga ---
if not api_key:
    st.warning("👈 Por favor, ingresá tu API Key en el panel izquierdo para comenzar.")
else:
    modo_carga = st.radio("Formato de subida:", ["Dos PDFs separados", "Un solo PDF (Remito + Factura)"], horizontal=True)

    df_remito = pd.DataFrame()
    df_factura = pd.DataFrame()
    texto_remito = ""
    texto_factura = ""
    procesado = False

    if modo_carga == "Un solo PDF (Remito + Factura)":
        archivo_unico = st.file_uploader("Subir PDF unificado", type=["pdf"])
        if archivo_unico:
            archivo_bytes = archivo_unico.getvalue()
            with pdfplumber.open(io.BytesIO(archivo_bytes)) as pdf:
                cant = len(pdf.pages)
            
            c1, c2 = st.columns(2)
            with c1: pag_remito = st.multiselect("Páginas Remito/Orden:", list(range(1, cant + 1)), default=[1])
            with c2: pag_factura = st.multiselect("Páginas Factura:", list(range(1, cant + 1)), default=[2] if cant > 1 else [1])
            
            if st.button("🚀 Extraer y Comparar"):
                with st.spinner("La IA está procesando los documentos..."):
                    texto_remito = extraer_texto_pdf(archivo_bytes, pag_remito)
                    texto_factura = extraer_texto_pdf(archivo_bytes, pag_factura)
                    df_remito = extraer_datos_con_ia(texto_remito, "Orden de Compra / Remito")
                    df_factura = extraer_datos_con_ia(texto_factura, "Factura")
                    procesado = True

    else:
        c1, c2 = st.columns(2)
        with c1: pdf_remito = st.file_uploader("Subir Remito/Orden", type=["pdf"])
        with c2: pdf_factura = st.file_uploader("Subir Factura", type=["pdf"])
        
        if pdf_remito and pdf_factura:
            if st.button("🚀 Extraer y Comparar"):
                with st.spinner("La IA está procesando los documentos..."):
                    texto_remito = extraer_texto_pdf(pdf_remito.getvalue(), [1]) 
                    texto_factura = extraer_texto_pdf(pdf_factura.getvalue(), [1])
                    df_remito = extraer_datos_con_ia(texto_remito, "Orden de Compra / Remito")
                    df_factura = extraer_datos_con_ia(texto_factura, "Factura")
                    procesado = True

    # --- Resultados y Cruce ---
    if procesado:
        st.divider()
        st.header("✅ Resultado del Análisis")
        
        # Mostramos qué leyó realmente el programa (para descartar que esté en blanco)
        with st.expander("👁️ Ver texto bruto extraído de los PDFs (Clic para abrir)"):
            st.text_area("Texto Remito", texto_remito, height=150)
            st.text_area("Texto Factura", texto_factura, height=150)
        
        if not df_remito.empty or not df_factura.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📋 Datos Orden/Remito")
                st.dataframe(df_remito, use_container_width=True) if not df_remito.empty else st.warning("Sin datos.")
            with c2:
                st.subheader("🧾 Datos Factura")
                st.dataframe(df_factura, use_container_width=True) if not df_factura.empty else st.warning("Sin datos.")

            st.divider()
            
            if not df_remito.empty and not df_factura.empty and 'codigo' in df_remito.columns and 'codigo' in df_factura.columns:
                st.header("⚖️ Conciliación Automática")
                
                df_remito['codigo'] = df_remito['codigo'].replace('', pd.NA).fillna(df_remito.get('descripcion', ''))
                df_factura['codigo'] = df_factura['codigo'].replace('', pd.NA).fillna(df_factura.get('descripcion', ''))
                
                df_cruce = pd.merge(df_remito, df_factura, on='codigo', how='outer', suffixes=('_remito', '_factura'))
                
                def a_numero(val):
                    try:
                        return float(str(val).replace(',', '.'))
                    except:
                        return 0.0
                
                df_cruce['cantidad_remito'] = df_cruce.get('cantidad_remito', pd.Series()).apply(a_numero)
                df_cruce['cantidad_factura'] = df_cruce.get('cantidad_factura', pd.Series()).apply(a_numero)
                df_cruce['diferencia_cant'] = df_cruce['cantidad_remito'] - df_cruce['cantidad_factura']
                
                st.write("Diferencias entre cantidades resaltadas en rojo.")
                
                def resaltar_diferencias(row):
                    if row['diferencia_cant'] != 0:
                        return ['background-color: #ffcccc'] * len(row)
                    return [''] * len(row)
                    
                st.dataframe(df_cruce.style.apply(resaltar_diferencias, axis=1), use_container_width=True)
            else:
                st.info("No se pudieron cruzar los datos porque falta la columna de códigos en uno de los archivos.")
