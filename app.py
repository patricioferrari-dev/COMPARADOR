import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import re
import fitz  # PyMuPDF
from PIL import Image

st.set_page_config(page_title="Comparador IA: Remito vs Factura", layout="wide")

st.title("🤖 Comparador IA (Procesamiento Fluido)")

# --- Configuración de la API ---
with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Ingresá tu API Key de Gemini:", type="password")

if api_key:
    genai.configure(api_key=api_key)

def obtener_modelo():
    # Intenta inicializar con los modelos disponibles
    for nombre in ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-3.8-flash']:
        try:
            m = genai.GenerativeModel(nombre)
            return m
        except:
            continue
    return genai.GenerativeModel('gemini-1.5-flash')

def procesar_pdf_como_imagen(pdf_bytes, paginas, tipo_doc, modelo):
    try:
        doc = fitz.open("pdf", pdf_bytes)
        imagenes = []
        
        for num in paginas:
            if 1 <= num <= len(doc):
                pagina = doc.load_page(num - 1)
                # Calidad optimizada para que sea ultra rápido el envío
                pix = pagina.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                imagenes.append(img)
                
        doc.close()
        
        if not imagenes:
            return []

        prompt = f"""
        Analizá el comprobante ({tipo_doc}).
        Extraé todos los artículos y devolvé ÚNICAMENTE un arreglo JSON con:
        [
          {{"codigo": "...", "descripcion": "...", "cantidad": 1.0, "precio": 0.0}}
        ]
        No agregues texto explicativo, solo el JSON.
        """
        
        respuesta = modelo.generate_content([prompt] + imagenes)
        
        match = re.search(r'\[.*\]', respuesta.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return []
            
    except Exception as e:
        st.error(f"Error en {tipo_doc}: {str(e)}")
        return []

# --- Interfaz y Procesamiento ---
if not api_key:
    st.warning("👈 Por favor, ingresá tu API Key en el panel izquierdo para comenzar.")
else:
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
                with st.spinner("Procesando rápida lectura visual..."):
                    modelo = obtener_modelo()
                    res_remito = procesar_pdf_como_imagen(archivo_bytes, pag_remito, "Remito", modelo)
                    res_factura = procesar_pdf_como_imagen(archivo_bytes, pag_factura, "Factura", modelo)
                    
                    st.session_state['df_remito'] = pd.DataFrame(res_remito)
                    st.session_state['df_factura'] = pd.DataFrame(res_factura)
                    st.session_state['listo'] = True

    else:
        c1, c2 = st.columns(2)
        with c1: pdf_remito = st.file_uploader("Subir Remito/Orden", type=["pdf"])
        with c2: pdf_factura = st.file_uploader("Subir Factura", type=["pdf"])
        
        if pdf_remito and pdf_factura:
            if st.button("🚀 Comparar Documentos"):
                with st.spinner("Procesando rápida lectura visual..."):
                    modelo = obtener_modelo()
                    res_remito = procesar_pdf_como_imagen(pdf_remito.getvalue(), [1], "Remito", modelo)
                    res_factura = procesar_pdf_como_imagen(pdf_factura.getvalue(), [1], "Factura", modelo)
                    
                    st.session_state['df_remito'] = pd.DataFrame(res_remito)
                    st.session_state['df_factura'] = pd.DataFrame(res_factura)
                    st.session_state['listo'] = True

    # --- Mostrar Resultados Persistentes ---
    if st.session_state.get('listo', False):
        df_remito = st.session_state.get('df_remito', pd.DataFrame())
        df_factura = st.session_state.get('df_factura', pd.DataFrame())
        
        st.divider()
        st.header("✅ Resultado del Análisis Visual")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📋 Datos Orden/Remito")
            st.dataframe(df_remito, use_container_width=True) if not df_remito.empty else st.warning("No se detectaron datos.")
        with c2:
            st.subheader("🧾 Datos Factura")
            st.dataframe(df_factura, use_container_width=True) if not df_factura.empty else st.warning("No se detectaron datos.")

        if not df_remito.empty and not df_factura.empty:
            st.divider()
            st.header("⚖️ Conciliación Automática")
            
            # Asignar clave para cruce
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
