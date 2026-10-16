import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import re
import fitz  # PyMuPDF
from PIL import Image

st.set_page_config(page_title="Comparador IA: Remito vs Factura", layout="wide")

st.title("🤖 Comparador IA Definitivo (Visión Real)")
st.write("Esta versión convierte los PDFs en imágenes y usa la visión de la IA para extraer los datos sin fallos.")

# --- Configuración de la API ---
with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Ingresá tu API Key de Gemini:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    modelo = genai.GenerativeModel('gemini-1.5-flash')

def procesar_pdf_como_imagen(pdf_bytes, paginas, tipo_doc):
    """Toma una 'foto' del PDF y se la envía a la IA."""
    try:
        doc = fitz.open("pdf", pdf_bytes)
        imagenes = []
        
        for num in paginas:
            if 1 <= num <= len(doc):
                pagina = doc.load_page(num - 1)
                # Genera una imagen nítida de la página
                pix = pagina.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                imagenes.append(img)
                
        if not imagenes:
            st.warning(f"No se pudieron generar imágenes para {tipo_doc}.")
            return pd.DataFrame()

        prompt = f"""
        Analizá las siguientes imágenes de un comprobante ({tipo_doc}).
        Extraé todos los artículos comerciales y devolvé ÚNICAMENTE un arreglo JSON válido con las claves: "codigo", "descripcion", "cantidad", "precio".
        Si falta un dato, usá un string vacío "" o 0.0 para números. No incluyas nada más que el JSON.
        """
        
        contenidos = [prompt] + imagenes
        respuesta = modelo.generate_content(contenidos)
        
        # Filtro de seguridad para limpiar texto extra si la IA habla de más
        match = re.search(r'\[.*\]', respuesta.text, re.DOTALL)
        if match:
            datos = json.loads(match.group(0))
            return pd.DataFrame(datos)
        else:
            st.error(f"La IA no devolvió un formato válido para {tipo_doc}.")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error procesando la imagen de {tipo_doc}: {str(e)}")
        return pd.DataFrame()

# --- Interfaz de Carga ---
if not api_key:
    st.warning("👈 Por favor, ingresá tu API Key en el panel izquierdo.")
else:
    modo_carga = st.radio("Formato de subida:", ["Dos PDFs separados", "Un solo PDF (Remito + Factura)"], horizontal=True)

    df_remito = pd.DataFrame()
    df_factura = pd.DataFrame()
    procesado = False

    if modo_carga == "Un solo PDF (Remito + Factura)":
        archivo_unico = st.file_uploader("Subir PDF unificado", type=["pdf"])
        if archivo_unico:
            archivo_bytes = archivo_unico.getvalue()
            doc_temp = fitz.open("pdf", archivo_bytes)
            cant = len(doc_temp)
            doc_temp.close()
            
            c1, c2 = st.columns(2)
            with c1: pag_remito = st.multiselect("Páginas Remito/Orden:", list(range(1, cant + 1)), default=[1])
            with c2: pag_factura = st.multiselect("Páginas Factura:", list(range(1, cant + 1)), default=[2] if cant > 1 else [1])
            
            if st.button("🚀 Extraer Visualmente y Comparar"):
                with st.spinner("Tomando fotos de los documentos y enviando a la IA..."):
                    df_remito = procesar_pdf_como_imagen(archivo_bytes, pag_remito, "Orden de Compra / Remito")
                    df_factura = procesar_pdf_como_imagen(archivo_bytes, pag_factura, "Factura")
                    procesado = True

    else:
        c1, c2 = st.columns(2)
        with c1: pdf_remito = st.file_uploader("Subir Remito/Orden", type=["pdf"])
        with c2: pdf_factura = st.file_uploader("Subir Factura", type=["pdf"])
        
        if pdf_remito and pdf_factura:
            if st.button("🚀 Extraer Visualmente y Comparar"):
                with st.spinner("Tomando fotos de los documentos y enviando a la IA..."):
                    df_remito = procesar_pdf_como_imagen(pdf_remito.getvalue(), [1], "Orden de Compra / Remito")
                    df_factura = procesar_pdf_como_imagen(pdf_factura.getvalue(), [1], "Factura")
                    procesado = True

    # --- Resultados y Cruce ---
    if procesado:
        st.divider()
        st.header("✅ Extracción Visual Exitosa")
        
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
                st.info("No se pudieron cruzar los datos porque falta la columna de códigos.")
