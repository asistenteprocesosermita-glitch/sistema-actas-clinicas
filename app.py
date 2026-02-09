import streamlit as st
import json
import io
import os
import requests
from datetime import datetime
import traceback

# Configuración de la página simple
st.set_page_config(
    page_title="Generador de Actas Clínicas",
    page_icon="📋",
    layout="wide"
)

# Título simple
st.title("📋 Generador Automático de Actas Clínicas")
st.markdown("Pega la transcripción de la reunión y genera el acta automáticamente.")

# Variables de estado
if 'api_key_configured' not in st.session_state:
    st.session_state.api_key_configured = False

# Verificar API Key
def check_api_key():
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("❌ API Key no configurada. Configura GEMINI_API_KEY en los secrets de Streamlit.")
        return False
    return True

# Cargar plantilla
def load_template():
    template_path = "ACTA DE REUNIÓN CLINICA LA ERMITA.docx"
    if os.path.exists(template_path):
        with open(template_path, "rb") as f:
            return f.read()
    else:
        st.error(f"❌ Plantilla no encontrada: {template_path}")
        st.info("Coloca la plantilla 'ACTA DE REUNIÓN CLINICA LA ERMITA.docx' en el mismo directorio que esta app.")
        return None

# Función para llamar a la API de Gemini
def call_gemini_api(prompt: str) -> str:
    api_key = st.secrets["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if "candidates" in result and result["candidates"]:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            raise ValueError("Respuesta de API vacía o mal formada")
            
    except Exception as e:
        raise Exception(f"Error en API: {str(e)}")

# Extraer JSON de la respuesta
def extract_json_from_response(response_text: str):
    text = response_text.strip()
    
    # Buscar JSON entre llaves
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start != -1 and end != 0:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except:
            pass
    
    # Intentar parsear directamente
    try:
        return json.loads(text)
    except:
        st.error(f"No se pudo extraer JSON. Respuesta: {text[:500]}")
        raise

# Interfaz principal
st.header("1. Transcripción de la Reunión")

transcription = st.text_area(
    "Pega aquí la transcripción completa de la reunión:",
    height=250,
    placeholder="Ejemplo: 'Buenos días, iniciamos la reunión a las 9:00 AM en la sede Pie de la Popa...'"
)

if st.button("🚀 Generar Acta Automáticamente", type="primary", use_container_width=True):
    if not check_api_key():
        st.stop()
    
    if not transcription.strip():
        st.warning("Por favor, pega una transcripción.")
        st.stop()
    
    template = load_template()
    if template is None:
        st.stop()
    
    with st.spinner("🤖 Analizando transcripción y generando acta..."):
        try:
            # Prompt optimizado para extraer TODA la información
            prompt = f"""Eres un asistente especializado en crear actas de reuniones clínicas para la Clínica La Ermita de Cartagena.

Analiza la siguiente transcripción y extrae TODA la información necesaria para completar un acta formal.

INSTRUCCIONES:
1. Extrae fecha, hora de inicio, hora de fin, ciudad y sede
2. Escribe un objetivo claro de la reunión
3. Identifica TODOS los temas discutidos (al menos 3-5)
4. Identifica TODOS los compromisos o acuerdos (al menos 2-4)
5. Identifica TODOS los participantes mencionados
6. Sugiere tema y fecha para próxima reunión si se menciona

TRANSCRIPCIÓN:
{transcription}

DEVUELVE SOLO UN JSON con esta estructura EXACTA:
{{
  "fecha": "DD/MM/YYYY",
  "hora_inicio": "HH:MM",
  "hora_fin": "HH:MM",
  "ciudad": "Cartagena",
  "sede": "Pie de la Popa o La Ermita",
  "objetivo": "texto descriptivo",
  "temas": [
    {{"i": 1, "tema": "título del tema", "desarrollo": "descripción detallada"}},
    {{"i": 2, "tema": "...", "desarrollo": "..."}}
  ],
  "compromisos": [
    {{"i": 1, "compromiso": "texto", "responsable": "nombre", "fecha": "DD/MM/YYYY o descripción"}},
    {{"i": 2, "compromiso": "...", "responsable": "...", "fecha": "..."}}
  ],
  "participantes": [
    {{"i": 1, "nombre": "Nombre completo", "cargo": "Cargo o función"}},
    {{"i": 2, "nombre": "...", "cargo": "..."}}
  ],
  "tema_proxima_reunion": "texto",
  "fecha_proxima_reunion": "texto"
}}

Si algún dato no está en la transcripción, usa valores apropiados basados en el contexto.
"""
            
            # Llamar a la API
            response_text = call_gemini_api(prompt)
            
            # Procesar respuesta
            data = extract_json_from_response(response_text)
            
            # Validar datos mínimos
            if "temas" not in data or not data["temas"]:
                data["temas"] = [{"i": 1, "tema": "Temas discutidos en la reunión", "desarrollo": "Se discutieron diversos puntos relacionados con el objetivo de la reunión."}]
            
            if "compromisos" not in data or not data["compromisos"]:
                data["compromisos"] = [{"i": 1, "compromiso": "Seguimiento de acuerdos", "responsable": "Por asignar", "fecha": "Por definir"}]
            
            if "participantes" not in data or not data["participantes"]:
                data["participantes"] = [{"i": 1, "nombre": "Participantes de la reunión", "cargo": "Varios cargos"}]
            
            # Generar documento Word
            from docxtpl import DocxTemplate
            
            # Preparar contexto para la plantilla
            context = {
                "FECHA": data.get("fecha", datetime.now().strftime("%d/%m/%Y")),
                "HORA_INICIO": data.get("hora_inicio", "09:00"),
                "HORA_FIN": data.get("hora_fin", "10:00"),
                "CIUDAD": data.get("ciudad", "Cartagena"),
                "SEDE": data.get("sede", "Pie de la Popa"),
                "OBJETIVO_DE_LA_REUNION": data.get("objetivo", "Reunión de trabajo clínico"),
                "TEMA_PROXIMA_REUNION": data.get("tema_proxima_reunion", "Seguimiento de acuerdos"),
                "FECHA_PROXIMA_REUNION": data.get("fecha_proxima_reunion", "Por definir"),
                "temas": data.get("temas", []),
                "compromisos": data.get("compromisos", []),
                "participantes": data.get("participantes", [])
            }
            
            # Renderizar plantilla
            template_stream = io.BytesIO(template)
            doc = DocxTemplate(template_stream)
            doc.render(context)
            
            # Guardar en memoria
            output_stream = io.BytesIO()
            doc.save(output_stream)
            output_stream.seek(0)
            
            # Crear nombre de archivo
            filename = f"ACTA_CLINICA_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
            
            # Mostrar éxito y botón de descarga
            st.success("✅ ¡Acta generada exitosamente!")
            
            # Mostrar resumen
            with st.expander("📋 Ver resumen del acta generada"):
                st.json(data)
            
            # Botón de descarga
            st.download_button(
                label="⬇️ Descargar Acta en Word",
                data=output_stream,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.code(traceback.format_exc(), language="python")

# Instrucciones simples en sidebar
with st.sidebar:
    st.header("ℹ️ Instrucciones")
    st.markdown("""
    1. **Pega** la transcripción completa
    2. **Haz clic** en "Generar Acta Automáticamente"
    3. **Descarga** el archivo Word generado
    
    La IA analizará automáticamente y completará:
    - Fecha, hora, ubicación
    - Objetivo de la reunión
    - Temas discutidos (con desarrollo)
    - Compromisos y responsables
    - Lista de participantes
    - Próxima reunión
    """)
    
    if check_api_key():
        st.success("✅ API Key configurada")
    
    st.divider()
    st.caption("Clínica La Ermita de Cartagena")
    st.caption(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}")
