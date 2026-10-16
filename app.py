import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import re
import fitz  # PyMuPDF
from PIL import Image

st.set_page_config(page_title="Comparador IA: Remito vs Factura", layout="wide")

st.title("🤖 Comparador IA (Modo Directo)")

# --- Configuración de la API ---
with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Ingresá tu API Key de Gemini:", type="password")

def extraer_json_de_texto(texto):
    """Extrae el bloque JSON de la respuesta de la IA."""
    try:
        match = re.search(r'\[.*\]', texto, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        match_obj = re.search(r'\{.*\}', texto, re.DOTALL)
        if match_obj:
            data = json.loads(match_obj.group(0))
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                for k in ['articulos', 'items', 'productos', 'remito', 'factura']:
                    if k in data and isinstance(data[k], list):
                        return data[k]
        return json.loads(texto)
    except Exception:
        return []

def procesar_pdf_como_imagen(pdf_bytes, paginas, tipo_doc, modelo):
    try:
        doc = fitz.open("pdf", pdf_bytes)
        imagenes = []
        
        for num in paginas:
            if 1 <= num <= len(doc):
                pagina = doc.load_page(num - 1)
                pix = pagina.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                imagenes.append(img)
                
        doc.close()
        
        if not imagenes:
            st.error(f"No se pudieron generar imágenes para {tipo_doc}.")
            return [], ""

        prompt = f"""
        Analizá este comprobante ({tipo_doc}).
        Extraé todos los artículos comerciales y devolvé ÚNICAMENTE un arreglo JSON con objetos que tengan las claves:
        "codigo", "descripcion", "cantidad", "precio".
        Si no hay código, poné "". Si no hay precio, poné 0.0.
        Devolvé SOLO el JSON sin explicaciones ni markdown.
        """
        
        respuesta = modelo.generate_content([prompt] + imagenes)
        raw_text = respuesta.text if hasattr(respuesta, 'text') else str(respuesta)
        
        datos = extraer_json_de_texto(raw_text)
        return datos, raw_text
            
    except Exception as e:
        st.error(f"Error procesando {tipo_doc}: {str(e)}")
        return [], str(e)

# --- Interfaz de Usuario ---
if not api_key:
    st.warning("👈 Por favor, ingresá tu API Key en el panel izquierdo para comenzar.")
else:
    genai.configure(api_key=api_key)
    
    # Modelo directo asignado
    try:
        modelo = genai.GenerativeModel('gemini-1.5-flash')
    except:
        modelo = genai.GenerativeModel('gemini-1.5-pro')

    modo_carga = st.radio("Formato de subida:", ["Dos PDFs separados", "Un solo PDF (Remito + Factura)"], horizontal=True)

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
            
            if st.button("🚀 Comparar Documentos"):
                with st.spinner("Procesando lectura visual con Gemini..."):
                    res_remito, raw_remito = procesar_pdf_como_imagen(archivo_bytes, pag_remito, "Remito", modelo)
                    res_factura, raw_factura = procesar_pdf_como_imagen(archivo_bytes, pag_factura, "Factura", modelo)
                    
                    st.divider()
                    st.header("🔍 Diagnóstico y Respuesta de la IA")
                    with st.expander("Ver respuesta en bruto de Gemini"):
                        st.subheader("Respuesta Remito")
                        st.code(raw_remito)
                        st.subheader("Respuesta Factura")
                        st.code(raw_factura)

                    df_remito = pd.DataFrame(res_remito)
                    df_factura = pd.DataFrame(res_factura)

                    st.divider()
                    st.header("✅ Resultado de la Extracción")
                    
                    c_a, c_b = st.columns(2)
                    with c_a:
                        st.subheader("📋 Datos Orden/Remito")
                        st.dataframe(df_remito, use_container_width=True) if not df_remito.empty else st.warning("No se extrajeron artículos del Remito.")
                    with c_b:
                        st.subheader("🧾 Datos Factura")
                        st.dataframe(df_factura, use_container_width=True) if not df_factura.empty else st.warning("No se extrajeron artículos de la Factura.")

                    if not df_remito.empty and not df_factura.empty:
                        st.divider()
                        st.header("⚖️ Conciliación Automática")
                        
                        col_rem = 'codigo' if 'codigo' in df_remito.columns and df_remito['codigo'].astype(bool).any() else 'descripcion'
                        col_fac = 'codigo' if 'codigo' in df_factura.columns and df_factura['codigo'].astype(bool).any() else 'descripcion'
                        
                        df_remito['clave'] = df_remito[col_rem]
                        df_factura['clave'] = df_factura[col_fac]
                        
                        df_cruce = pd.merge(df_remito, df_factura, on='clave', how='outer', suffixes=('_remito', '_factura'))
                        
                        def a_numero(val):
                            try:
                                return float(str(val).replace(',', '.'))
                            except:
                                return 0.0
                        
                        df_cruce['cant_remito'] = df_cruce.get('cantidad_remito', pd.Series()).apply(a_numero)
                        df_cruce['cant_factura'] = df_cruce.get('cantidad_factura', pd.Series()).apply(a_numero)
                        df_cruce['diferencia'] = df_cruce['cant_remito'] - df_cruce['cant_factura']
                        
                        def resaltar_diferencias(row):
                            if row['diferencia'] != 0:
                                return ['background-color: #ffcccc'] * len(row)
                            return [''] * len(row)
                            
                        st.dataframe(df_cruce.style.apply(resaltar_diferencias, axis=1), use_container_width=True)

    else:
        c1, c2 = st.columns(2)
        with c1: pdf_remito = st.file_uploader("Subir Remito/Orden", type=["pdf"])
        with c2: pdf_factura = st.file_uploader("Subir Factura", type=["pdf"])
        
        if pdf_remito and pdf_factura:
            if st.button("🚀 Comparar Documentos"):
                with st.spinner("Procesando lectura visual con Gemini..."):
                    res_remito, raw_remito = procesar_pdf_como_imagen(pdf_remito.getvalue(), [1], "Remito", modelo)
                    res_factura, raw_factura = procesar_pdf_como_imagen(pdf_factura.getvalue(), [1], "Factura", modelo)
                    
                    st.divider()
                    st.header("🔍 Diagnóstico y Respuesta de la IA")
                    with st.expander("Ver respuesta en bruto de Gemini"):
                        st.subheader("Respuesta Remito")
                        st.code(raw_remito)
                        st.subheader("Respuesta Factura")
                        st.code(raw_factura)

                    df_remito = pd.DataFrame(res_remito)
                    df_factura = pd.DataFrame(res_factura)

                    st.divider()
                    st.header("✅ Resultado de la Extracción")
                    
                    c_a, c_b = st.columns(2)
                    with c_a:
                        st.subheader("📋 Datos Orden/Remito")
                        st.dataframe(df_remito, use_container_width=True) if not df_remito.empty else st.warning("No se extrajeron artículos del Remito.")
                    with c_b:
                        st.subheader("🧾 Datos Factura")
                        st.dataframe(df_factura, use_container_width=True) if not df_factura.empty else st.warning("No se extrajeron artículos de la Factura.")

                    if not df_remito.empty and not df_factura.empty:
                        st.divider()
                        st.header("⚖️ Conciliación Automática")
                        
                        col_rem = 'codigo' if 'codigo' in df_remito.columns and df_remito['codigo'].astype(bool).any() else 'descripcion'
                        col_fac = 'codigo' if 'codigo' in df_factura.columns and df_factura['codigo'].astype(bool).any() else 'descripcion'
                        
                        df_remito['clave'] = df_remito[col_rem]
                        df_factura['clave'] = df_factura[col_fac]
                        
                        df_cruce = pd.merge(df_remito, df_factura, on='clave', how='outer', suffixes=('_remito', '_factura'))
                        
                        def a_numero(val):
                            try:
                                return float(str(val).replace(',', '.'))
                            except:
                                return 0.0
                        
                        df_cruce['cant_remito'] = df_cruce.get('cantidad_remito', pd.Series()).apply(a_numero)
                        df_cruce['cant_factura'] = df_cruce.get('cantidad_factura', pd.Series()).apply(a_numero)
                        df_cruce['diferencia'] = df_cruce['cant_remito'] - df_cruce['cant_factura']
                        
                        def resaltar_diferencias(row):
                            if row['diferencia'] != 0:
                                return ['background-color: #ffcccc'] * len(row)
                            return [''] * len(row)
                            
                        st.dataframe(df_cruce.style.apply(resaltar_diferencias, axis=1), use_container_width=True)
            st.dataframe(df_cruce.style.apply(resaltar_diferencias, axis=1), use_container_width=True)
