import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

st.set_page_config(page_title="Comparador IA: Remito vs Factura", layout="wide")

st.title("🤖 Comparador IA (Visión Óptica)")
st.write("Sube tus PDFs. La Inteligencia Artificial 'leerá' visualmente los documentos (incluso si son imágenes escaneadas) y hará el cruce.")

# --- Configuración de la API ---
with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Ingresá tu API Key de Gemini:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    # Usamos Gemini 1.5 Flash que tiene soporte nativo para procesar archivos PDF visualmente
    modelo = genai.GenerativeModel('gemini-1.5-flash')

def procesar_documento_ia(archivo_bytes, prompt):
    """Envía el PDF crudo directamente a los 'ojos' de Gemini para que haga OCR y lo estructure."""
    pdf_part = {
        "mime_type": "application/pdf",
        "data": archivo_bytes
    }
    
    try:
        respuesta = modelo.generate_content(
            [prompt, pdf_part],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(respuesta.text)
    except Exception as e:
        st.error("Hubo un error al procesar la imagen del PDF.")
        st.info(f"Detalle técnico: {str(e)}")
        return None

# --- Interfaz de Carga ---
if not api_key:
    st.warning("👈 Por favor, ingresá tu API Key en el panel izquierdo para comenzar.")
else:
    modo_carga = st.radio("Formato de subida:", ["Dos PDFs separados", "Un solo PDF (Remito + Factura mezclados)"], horizontal=True)

    df_remito = pd.DataFrame()
    df_factura = pd.DataFrame()
    listo_para_comparar = False

    if modo_carga == "Dos PDFs separados":
        c1, c2 = st.columns(2)
        with c1: pdf_remito = st.file_uploader("Subir Remito / Orden de Compra", type=["pdf"])
        with c2: pdf_factura = st.file_uploader("Subir Factura", type=["pdf"])
        
        if pdf_remito and pdf_factura:
            if st.button("🚀 Extraer con Visión IA y Comparar"):
                with st.spinner("La IA está analizando visualmente las imágenes de los documentos..."):
                    
                    prompt_base = """
                    Sos un contador experto. Analizá el PDF adjunto visualmente.
                    Extraé todos los artículos comerciales listados.
                    Devolvé ÚNICAMENTE un JSON con un arreglo de objetos. Cada objeto debe tener:
                    "codigo", "descripcion", "cantidad", "precio".
                    Si no hay código, dejá un string vacío "". Si no hay precio, poné 0.0.
                    """
                    
                    datos_remito = procesar_documento_ia(pdf_remito.getvalue(), prompt_base + " El documento es un Remito u Orden de Compra.")
                    datos_factura = procesar_documento_ia(pdf_factura.getvalue(), prompt_base + " El documento es una Factura.")
                    
                    if datos_remito and datos_factura:
                        df_remito = pd.DataFrame(datos_remito)
                        df_factura = pd.DataFrame(datos_factura)
                        listo_para_comparar = True

    else:
        archivo_unico = st.file_uploader("Subir el PDF unificado", type=["pdf"])
        
        if archivo_unico:
            if st.button("🚀 Extraer con Visión IA y Comparar"):
                with st.spinner("La IA está leyendo y separando el PDF unificado..."):
                    
                    prompt_unificado = """
                    Sos un contador experto. Analizá visualmente el PDF adjunto. 
                    El documento contiene páginas que corresponden a una Orden de Compra/Remito y páginas que corresponden a una Factura.
                    Extraé los artículos de AMBOS y separalos.
                    Devolvé ÚNICAMENTE un objeto JSON con dos claves exactas: "remito" y "factura".
                    Cada clave debe contener un arreglo de objetos con: "codigo", "descripcion", "cantidad", "precio".
                    """
                    
                    resultado = procesar_documento_ia(archivo_unico.getvalue(), prompt_unificado)
                    
                    # CORREGIDO AQUÍ: se usa "and" en vez de "y"
                    if resultado and "remito" in resultado and "factura" in resultado:
                        df_remito = pd.DataFrame(resultado["remito"])
                        df_factura = pd.DataFrame(resultado["factura"])
                        listo_para_comparar = True

    # --- Resultados y Cruce ---
    if listo_para_comparar and not df_remito.empty and not df_factura.empty:
        st.divider()
        st.header("✅ Extracción Visual Exitosa")
        
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
            # Rellenar códigos vacíos con la descripción para que pueda hacer el cruce si no hay código
            df_remito['codigo'] = df_remito['codigo'].replace('', pd.NA).fillna(df_remito['descripcion'])
            df_factura['codigo'] = df_factura['codigo'].replace('', pd.NA).fillna(df_factura['descripcion'])
            
            df_cruce = pd.merge(df_remito, df_factura, on='codigo', how='outer', suffixes=('_remito', '_factura'))
            
            # Cálculo de diferencias
            df_cruce['diferencia_cant'] = pd.to_numeric(df_cruce['cantidad_remito'], errors='coerce').fillna(0) - pd.to_numeric(df_cruce['cantidad_factura'], errors='coerce').fillna(0)
            
            st.write("Comparamos los artículos. Las filas con diferencias están resaltadas en rojo.")
            
            def resaltar_diferencias(row):
                if row['diferencia_cant'] != 0:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)
                
            st.dataframe(df_cruce.style.apply(resaltar_diferencias, axis=1), use_container_width=True)
        else:
            st.warning("No se pudo realizar el cruce automático.")
