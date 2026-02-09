import streamlit as st
import json
import io
import os
from datetime import datetime
from typing import Dict, List, Any
import traceback

# Configuración de la página
st.set_page_config(
    page_title="Automatización de Actas Clínicas",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Título y descripción
st.title("📋 Sistema de Automatización de Actas Clínicas")
st.markdown("""
Transforma transcripciones de reuniones en actas formales listas para usar.
Utiliza IA para extraer información y genera documentos Word con formato profesional.
""")

# Inicialización de variables en session_state
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None
if 'edited_data' not in st.session_state:
    st.session_state.edited_data = None

# --- FUNCIONES AUXILIARES ---
def validate_api_key():
    """Valida que la API key esté configurada"""
    if "GEMINI_API_KEY" not in st.secrets or not st.secrets["GEMINI_API_KEY"]:
        st.error("⚠️ API Key de Gemini no encontrada en st.secrets")
        st.info("Por favor, configura la variable GEMINI_API_KEY en tus secrets de Streamlit")
        return False
    return True

def load_template():
    """Carga la plantilla Word desde el sistema de archivos"""
    template_path = "ACTA DE REUNIÓN CLINICA LA ERMITA.docx"
    
    try:
        # Primero intentamos cargar desde la ruta especificada
        if os.path.exists(template_path):
            with open(template_path, "rb") as f:
                return f.read()
        else:
            # Si no existe, mostramos instrucciones
            st.warning(f"📄 Plantilla no encontrada en: {os.path.abspath(template_path)}")
            st.info("""
            **Para usar esta aplicación, necesitas:**
            1. Colocar tu plantilla Word en el mismo directorio que esta app
            2. Nombrarla: `ACTA DE REUNIÓN CLINICA LA ERMITA.docx`
            3. Asegurarte de que tenga las etiquetas correctas:
               - {{FECHA}}, {{HORA_INICIO}}, {{HORA_FIN}}, {{CIUDAD}}, {{SEDE}}
               - {{OBJETIVO_DE_LA_REUNION}}
               - Tablas dinámicas con {{tema}}, {{desarrollo}}, {{compromiso}}, {{responsable}}, {{fecha}}, {{nombre}}, {{cargo}}
            """)
            return None
    except Exception as e:
        st.error(f"❌ Error al cargar la plantilla: {str(e)}")
        return None

# --- SECCIÓN DE EXTRACCIÓN CON IA ---
st.header("1. Extracción de Información con IA")

# Input para la transcripción
transcription = st.text_area(
    "📝 **Transcripción de la reunión:**",
    height=200,
    placeholder="Pega aquí la transcripción completa de la reunión. Incluye:\n• Fecha y hora\n• Participantes\n• Temas discutidos\n• Compromisos acordados\n• Cualquier información relevante",
    help="Cuanta más información proporciones, más precisa será la extracción."
)

# Botón para extraer información
if st.button("🔍 Extraer Información con IA", type="primary", use_container_width=True):
    if not validate_api_key():
        st.stop()
    
    if not transcription.strip():
        st.warning("Por favor, ingresa una transcripción primero.")
        st.stop()
    
    # Cargamos la plantilla para verificar que existe
    template_content = load_template()
    if template_content is None:
        st.stop()
    
    with st.spinner("🤖 Analizando transcripción con IA..."):
        try:
            # Importamos Gemini solo cuando sea necesario
            import google.generativeai as genai
            
            # Configurar la API
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # Definir el prompt estricto para extracción
            prompt = f"""
            Eres un asistente especializado en extraer información estructurada de transcripciones de reuniones clínicas.
            
            INSTRUCCIONES ESTRICTAS:
            1. Analiza la siguiente transcripción y extrae ÚNICAMENTE la información solicitada.
            2. Devuelve EXCLUSIVAMENTE un objeto JSON válido, sin texto adicional, sin markdown, sin explicaciones.
            3. El JSON debe tener EXACTAMENTE la siguiente estructura:
            
            {{
                "fecha": "string (formato DD/MM/YYYY)",
                "hora_inicio": "string (formato HH:MM)",
                "hora_fin": "string (formato HH:MM)",
                "ciudad": "string",
                "sede": "string",
                "objetivo": "string (descripción clara del objetivo de la reunión)",
                "temas": [
                    {{
                        "tema": "string",
                        "desarrollo": "string (descripción detallada)"
                    }}
                ],
                "compromisos": [
                    {{
                        "compromiso": "string",
                        "responsable": "string",
                        "fecha": "string (formato DD/MM/YYYY o descripción relativa)"
                    }}
                ],
                "participantes": [
                    {{
                        "nombre": "string",
                        "cargo": "string"
                    }}
                ]
            }}
            
            4. Reglas específicas:
               - Si algún campo no puede determinarse, usar cadena vacía ""
               - Para fecha/hora: extraer de la transcripción, si no está, dejar vacío
               - Para participantes: listar todos los mencionados con nombre y cargo
               - Para temas: extraer cada tema discutido con su desarrollo
               - Para compromisos: extraer acuerdos específicos con responsables y fechas
            
            TRANSCRIPCIÓN A ANALIZAR:
            {transcription}
            
            RESPUESTA (SOLO JSON):
            """
            
            # Usar el modelo Gemini
            model = genai.GenerativeModel('gemini-3-flash')
            response = model.generate_content(prompt)
            
            # Intentar parsear el JSON
            try:
                # Limpiar la respuesta (por si acaso hay texto adicional)
                response_text = response.text.strip()
                
                # Buscar el JSON en la respuesta (por si hay texto alrededor)
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                
                if start_idx != -1 and end_idx != 0:
                    json_str = response_text[start_idx:end_idx]
                    extracted_data = json.loads(json_str)
                    
                    # Validar estructura básica
                    required_keys = ["fecha", "hora_inicio", "hora_fin", "ciudad", "sede", 
                                   "objetivo", "temas", "compromisos", "participantes"]
                    
                    if all(key in extracted_data for key in required_keys):
                        st.session_state.extracted_data = extracted_data
                        st.session_state.edited_data = extracted_data.copy()
                        st.success("✅ Información extraída exitosamente!")
                    else:
                        st.error("⚠️ La IA no devolvió la estructura esperada")
                        st.json(extracted_data)  # Mostrar lo que sí devolvió
                else:
                    st.error("❌ No se pudo encontrar JSON en la respuesta de la IA")
                    st.code(response_text, language="text")
                    
            except json.JSONDecodeError as e:
                st.error(f"❌ Error al parsear JSON: {str(e)}")
                st.code(response.text, language="text")
                
        except Exception as e:
            st.error(f"❌ Error al comunicarse con la IA: {str(e)}")
            st.error(traceback.format_exc())

# --- SECCIÓN DE EDICIÓN Y VALIDACIÓN ---
if st.session_state.extracted_data:
    st.header("2. Validación y Edición de Datos")
    st.info("Revisa y edita la información extraída antes de generar el documento.")
    
    data = st.session_state.extracted_data
    edited_data = {}
    
    # Crear pestañas para organizar la edición
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Información Básica", "📊 Temas", "✅ Compromisos", "👥 Participantes"])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            edited_data["fecha"] = st.text_input("Fecha", value=data.get("fecha", ""))
            edited_data["hora_inicio"] = st.text_input("Hora de Inicio", value=data.get("hora_inicio", ""))
            edited_data["ciudad"] = st.text_input("Ciudad", value=data.get("ciudad", ""))
        
        with col2:
            edited_data["hora_fin"] = st.text_input("Hora de Fin", value=data.get("hora_fin", ""))
            edited_data["sede"] = st.text_input("Sede", value=data.get("sede", ""))
        
        edited_data["objetivo"] = st.text_area(
            "Objetivo de la Reunión", 
            value=data.get("objetivo", ""),
            height=100
        )
    
    with tab2:
        st.subheader("Temas del Orden del Día")
        
        # Inicializar lista de temas si no existe
        temas = data.get("temas", [])
        if not temas:
            temas = [{"tema": "", "desarrollo": ""}]
        
        edited_temas = []
        for i, tema in enumerate(temas, 1):
            st.markdown(f"**Tema {i}**")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                nuevo_tema = st.text_input(f"Título del Tema {i}", 
                                         value=tema.get("tema", ""),
                                         key=f"tema_{i}")
            
            with col2:
                nuevo_desarrollo = st.text_area(f"Desarrollo del Tema {i}",
                                              value=tema.get("desarrollo", ""),
                                              height=100,
                                              key=f"desarrollo_{i}")
            
            edited_temas.append({
                "tema": nuevo_tema,
                "desarrollo": nuevo_desarrollo
            })
            
            st.divider()
        
        # Botón para agregar más temas
        if st.button("➕ Agregar otro tema"):
            edited_temas.append({"tema": "", "desarrollo": ""})
            st.rerun()
        
        edited_data["temas"] = edited_temas
    
    with tab3:
        st.subheader("Compromisos Acordados")
        
        # Inicializar lista de compromisos si no existe
        compromisos = data.get("compromisos", [])
        if not compromisos:
            compromisos = [{"compromiso": "", "responsable": "", "fecha": ""}]
        
        edited_compromisos = []
        for i, compromiso in enumerate(compromisos, 1):
            st.markdown(f"**Compromiso {i}**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                nuevo_compromiso = st.text_input(f"Compromiso {i}",
                                               value=compromiso.get("compromiso", ""),
                                               key=f"compromiso_{i}")
            
            with col2:
                nuevo_responsable = st.text_input(f"Responsable {i}",
                                                value=compromiso.get("responsable", ""),
                                                key=f"responsable_{i}")
            
            with col3:
                nuevo_fecha = st.text_input(f"Fecha de Ejecución {i}",
                                          value=compromiso.get("fecha", ""),
                                          key=f"fecha_comp_{i}")
            
            edited_compromisos.append({
                "compromiso": nuevo_compromiso,
                "responsable": nuevo_responsable,
                "fecha": nuevo_fecha
            })
            
            st.divider()
        
        # Botón para agregar más compromisos
        if st.button("➕ Agregar otro compromiso"):
            edited_compromisos.append({"compromiso": "", "responsable": "", "fecha": ""})
            st.rerun()
        
        edited_data["compromisos"] = edited_compromisos
    
    with tab4:
        st.subheader("Participantes")
        
        # Inicializar lista de participantes si no existe
        participantes = data.get("participantes", [])
        if not participantes:
            participantes = [{"nombre": "", "cargo": ""}]
        
        edited_participantes = []
        for i, participante in enumerate(participantes, 1):
            st.markdown(f"**Participante {i}**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_nombre = st.text_input(f"Nombre {i}",
                                           value=participante.get("nombre", ""),
                                           key=f"nombre_{i}")
            
            with col2:
                nuevo_cargo = st.text_input(f"Cargo {i}",
                                          value=participante.get("cargo", ""),
                                          key=f"cargo_{i}")
            
            edited_participantes.append({
                "nombre": nuevo_nombre,
                "cargo": nuevo_cargo
            })
            
            st.divider()
        
        # Botón para agregar más participantes
        if st.button("➕ Agregar otro participante"):
            edited_participantes.append({"nombre": "", "cargo": ""})
            st.rerun()
        
        edited_data["participantes"] = edited_participantes
    
    # Guardar datos editados
    st.session_state.edited_data = edited_data
    
    # --- SECCIÓN DE GENERACIÓN DEL DOCUMENTO ---
    st.header("3. Generación del Documento")
    
    if st.button("📄 Generar Acta en Word", type="primary", use_container_width=True):
        if not validate_api_key():
            st.stop()
        
        template_content = load_template()
        if template_content is None:
            st.stop()
        
        with st.spinner("🔄 Generando documento Word..."):
            try:
                # Importar docxtpl solo cuando sea necesario
                from docxtpl import DocxTemplate
                
                # Guardar datos editados
                final_data = st.session_state.edited_data
                
                # Preparar contexto para la plantilla
                context = {
                    "FECHA": final_data.get("fecha", ""),
                    "HORA_INICIO": final_data.get("hora_inicio", ""),
                    "HORA_FIN": final_data.get("hora_fin", ""),
                    "CIUDAD": final_data.get("ciudad", ""),
                    "SEDE": final_data.get("sede", ""),
                    "OBJETIVO_DE_LA_REUNION": final_data.get("objetivo", ""),
                }
                
                # Agregar tablas dinámicas
                context["temas"] = final_data.get("temas", [])
                context["compromisos"] = final_data.get("compromisos", [])
                context["participantes"] = final_data.get("participantes", [])
                
                # Usar BytesIO para manejar la plantilla en memoria
                template_stream = io.BytesIO(template_content)
                
                # Cargar plantilla desde el stream
                doc = DocxTemplate(template_stream)
                
                # Renderizar plantilla con los datos
                doc.render(context)
                
                # Guardar el documento en memoria
                output_stream = io.BytesIO()
                doc.save(output_stream)
                output_stream.seek(0)
                
                # Crear nombre de archivo con fecha
                fecha_actual = datetime.now().strftime("%Y%m%d_%H%M")
                filename = f"ACTA_CLINICA_{fecha_actual}.docx"
                
                # Botón de descarga
                st.download_button(
                    label="⬇️ Descargar Acta de Reunión",
                    data=output_stream,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    type="primary"
                )
                
                st.success("✅ Documento generado exitosamente!")
                st.info("Haz clic en el botón de arriba para descargar el archivo Word.")
                
            except Exception as e:
                st.error(f"❌ Error al generar el documento: {str(e)}")
                st.error(traceback.format_exc())

# --- SECCIÓN DE PREVISUALIZACIÓN ---
if st.session_state.edited_data:
    st.header("📋 Previsualización de Datos")
    
    with st.expander("Ver datos estructurados"):
        st.json(st.session_state.edited_data)
    
    # Mostrar resumen visual
    data = st.session_state.edited_data
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("📅 Fecha", data.get("fecha", "No especificada"))
        st.metric("🏙️ Ciudad", data.get("ciudad", "No especificada"))
        st.metric("📊 Temas", len(data.get("temas", [])))
    
    with col2:
        st.metric("⏰ Duración", f"{data.get('hora_inicio', '')} - {data.get('hora_fin', '')}")
        st.metric("📍 Sede", data.get("sede", "No especificada"))
        st.metric("👥 Participantes", len(data.get("participantes", [])))

# --- INSTRUCCIONES EN EL SIDEBAR ---
with st.sidebar:
    st.header("ℹ️ Instrucciones")
    
    st.markdown("""
    ### Flujo de Trabajo:
    1. **Pega** la transcripción de la reunión
    2. **Haz clic** en "Extraer Información con IA"
    3. **Revisa y edita** los datos extraídos
    4. **Genera** el documento Word
    5. **Descarga** el acta lista
    
    ### Requisitos:
    • API Key de Gemini configurada en secrets
    • Plantilla Word en el directorio de la app
    • Transcripción lo más completa posible
    
    ### Etiquetas de la Plantilla:
    La plantilla debe contener estas etiquetas:
    - `{{FECHA}}`, `{{HORA_INICIO}}`, `{{HORA_FIN}}`
    - `{{CIUDAD}}`, `{{SEDE}}`
    - `{{OBJETIVO_DE_LA_REUNION}}`
    - Tablas con: `{{tema}}`, `{{desarrollo}}`
    - Tablas con: `{{compromiso}}`, `{{responsable}}`, `{{fecha}}`
    - Tablas con: `{{nombre}}`, `{{cargo}}`
    """)
    
    st.divider()
    
    # Verificar estado de la API
    if validate_api_key():
        st.success("✅ API Key configurada")
    else:
        st.error("❌ API Key no encontrada")
    
    # Verificar plantilla
    template_content = load_template()
    if template_content:
        st.success("✅ Plantilla encontrada")
    else:
        st.error("❌ Plantilla no encontrada")

# --- PIE DE PÁGINA ---
st.divider()
st.caption("Sistema de Automatización de Actas Clínicas | Clínica La Ermita | v1.0")
