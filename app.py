import streamlit as st
import json
import io
import os
import sys
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
if 'template_content' not in st.session_state:
    st.session_state.template_content = None
if 'available_models' not in st.session_state:
    st.session_state.available_models = []

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
    if st.session_state.template_content is not None:
        return st.session_state.template_content
    
    template_path = "ACTA DE REUNIÓN CLINICA LA ERMITA.docx"
    
    try:
        # Primero intentamos cargar desde la ruta especificada
        if os.path.exists(template_path):
            with open(template_path, "rb") as f:
                st.session_state.template_content = f.read()
                return st.session_state.template_content
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

def get_available_models():
    """Obtiene los modelos disponibles de la API"""
    try:
        import google.generativeai as genai
        
        if not validate_api_key():
            return []
        
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # Lista de modelos a probar (ordenados por prioridad)
        models_to_try = [
            "gemini-1.5-flash",  # Primera opción
            "gemini-1.0-pro",    # Segunda opción
            "gemini-pro",        # Tercera opción
            "models/gemini-pro", # Cuarta opción
            "gemini-1.5-pro",    # Quinta opción
        ]
        
        available = []
        
        # Probar cada modelo
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                # Intentar una consulta simple para verificar
                response = model.generate_content("Test")
                if response and response.text:
                    available.append(model_name)
                    st.success(f"✅ Modelo encontrado: {model_name}")
                    return [model_name]  # Retornar el primero que funcione
            except Exception as e:
                if "404" not in str(e):  # Solo mostrar errores que no sean 404
                    st.warning(f"⚠️ Error con modelo {model_name}: {str(e)[:100]}")
                continue
        
        return available
    except Exception as e:
        st.error(f"❌ Error al obtener modelos: {str(e)}")
        return []

def extract_json_from_response(response_text: str) -> Dict:
    """Extrae JSON de la respuesta de la IA, manejando diferentes formatos"""
    try:
        # Limpiar la respuesta
        text = response_text.strip()
        
        # Método 1: Intentar parsear directamente
        try:
            return json.loads(text)
        except:
            pass
        
        # Método 2: Buscar JSON entre llaves
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != 0:
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
        
        # Método 3: Si la respuesta contiene ```json o ```
        if '```json' in text:
            parts = text.split('```json')
            if len(parts) > 1:
                json_part = parts[1].split('```')[0].strip()
                return json.loads(json_part)
        
        if '```' in text:
            parts = text.split('```')
            if len(parts) > 1:
                # Buscar la parte que parece JSON
                for part in parts:
                    part = part.strip()
                    if part.startswith('{') and part.endswith('}'):
                        return json.loads(part)
        
        raise ValueError("No se pudo extraer JSON de la respuesta")
        
    except Exception as e:
        st.error(f"Error procesando respuesta de la IA: {str(e)}")
        st.code(text, language="text")
        raise

# --- SECCIÓN DE EXTRACCIÓN CON IA ---
st.header("1. Extracción de Información con IA")

# Primero obtener modelos disponibles si no lo hemos hecho
if not st.session_state.available_models:
    if st.button("🔍 Detectar Modelos Disponibles", type="secondary"):
        with st.spinner("Buscando modelos disponibles..."):
            st.session_state.available_models = get_available_models()
            
            if st.session_state.available_models:
                st.success(f"Modelos detectados: {', '.join(st.session_state.available_models)}")
            else:
                st.error("No se encontraron modelos disponibles. Verifica tu API Key.")

# Si tenemos modelos disponibles, mostrar selector
if st.session_state.available_models:
    model_option = st.selectbox(
        "Selecciona el modelo de IA:",
        st.session_state.available_models,
        index=0,
        help="Modelos disponibles detectados en tu API"
    )
else:
    # Si no hay modelos detectados, usar uno por defecto
    model_option = "gemini-1.0-pro"
    st.warning("⚠️ Usando modelo por defecto. Presiona 'Detectar Modelos Disponibles' para verificar.")

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
            EXTRACCIÓN ESTRUCTURADA DE REUNIÓN CLÍNICA
            
            INSTRUCCIONES ABSOLUTAS:
            1. Analiza EXCLUSIVAMENTE la transcripción proporcionada
            2. Extrae ÚNICAMENTE los datos solicitados
            3. Devuelve EXCLUSIVAMENTE un objeto JSON válido
            4. NO incluyas texto, explicaciones, ni markdown
            5. NO añadas comentarios ni notas
            
            ESTRUCTURA JSON OBLIGATORIA:
            {{
                "fecha": "string (formato DD/MM/YYYY)",
                "hora_inicio": "string (formato HH:MM)",
                "hora_fin": "string (formato HH:MM)",
                "ciudad": "string",
                "sede": "string",
                "objetivo": "string",
                "temas": [
                    {{
                        "tema": "string",
                        "desarrollo": "string"
                    }}
                ],
                "compromisos": [
                    {{
                        "compromiso": "string",
                        "responsable": "string",
                        "fecha": "string"
                    }}
                ],
                "participantes": [
                    {{
                        "nombre": "string",
                        "cargo": "string"
                    }}
                ]
            }}
            
            REGLAS DE EXTRACCIÓN:
            - Fecha: Extraer en formato DD/MM/YYYY. Si no se encuentra, usar ""
            - Hora: Formato 24h HH:MM. Si no se encuentra, usar ""
            - Ciudad/Sede: Nombres completos. Si no se encuentran, usar ""
            - Objetivo: Frase clara y concisa del propósito principal
            - Temas: Cada punto del orden del día con desarrollo detallado
            - Compromisos: Acuerdos específicos con responsables y fechas
            - Participantes: Lista completa con nombre y cargo
            
            TRANSCRIPCIÓN:
            {transcription}
            
            RESPUESTA (SOLO JSON):
            """
            
            # Intentar usar el modelo seleccionado
            try:
                st.info(f"Intentando con modelo: {model_option}")
                model = genai.GenerativeModel(model_option)
                
                # Configurar parámetros de generación
                generation_config = {
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 4096,
                }
                
                # Generar respuesta
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
            except Exception as model_error:
                st.warning(f"Modelo {model_option} falló: {str(model_error)[:100]}")
                
                # Intentar con modelo alternativo
                try:
                    st.info("Intentando con modelo alternativo: gemini-1.0-pro")
                    model = genai.GenerativeModel("gemini-1.0-pro")
                    response = model.generate_content(prompt)
                except Exception as alt_error:
                    st.error(f"Todos los modelos fallaron. Error: {str(alt_error)[:200]}")
                    st.stop()
            
            # Procesar respuesta
            if response and response.text:
                try:
                    extracted_data = extract_json_from_response(response.text)
                    
                    # Validar estructura básica
                    required_keys = ["fecha", "hora_inicio", "hora_fin", "ciudad", "sede", 
                                   "objetivo", "temas", "compromisos", "participantes"]
                    
                    # Asegurar que todos los campos existan
                    for key in required_keys:
                        if key not in extracted_data:
                            extracted_data[key] = ""
                    
                    # Asegurar que las listas sean listas
                    if not isinstance(extracted_data.get("temas"), list):
                        extracted_data["temas"] = []
                    if not isinstance(extracted_data.get("compromisos"), list):
                        extracted_data["compromisos"] = []
                    if not isinstance(extracted_data.get("participantes"), list):
                        extracted_data["participantes"] = []
                    
                    st.session_state.extracted_data = extracted_data
                    st.session_state.edited_data = extracted_data.copy()
                    st.success("✅ Información extraída exitosamente!")
                    
                    # Mostrar vista previa
                    with st.expander("📊 Vista previa de datos extraídos", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Fecha", extracted_data.get("fecha", "No especificada"))
                            st.metric("Horario", f"{extracted_data.get('hora_inicio', '')} - {extracted_data.get('hora_fin', '')}")
                        with col2:
                            st.metric("Ubicación", f"{extracted_data.get('ciudad', '')} - {extracted_data.get('sede', '')}")
                            st.metric("Participantes", len(extracted_data.get("participantes", [])))
                        
                        st.caption(f"**Objetivo:** {extracted_data.get('objetivo', '')}")
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar la respuesta de la IA: {str(e)}")
                    st.error("La IA no devolvió un JSON válido.")
                    if hasattr(response, 'text'):
                        st.code(response.text[:500] + "..." if len(response.text) > 500 else response.text, language="text")
            else:
                st.error("❌ La IA no devolvió ninguna respuesta")
                
        except Exception as e:
            st.error(f"❌ Error al comunicarse con la IA: {str(e)}")
            st.error(traceback.format_exc())

# --- SECCIÓN DE EDICIÓN Y VALIDACIÓN ---
if st.session_state.extracted_data:
    st.header("2. Validación y Edición de Datos")
    st.info("Revisa y edita la información extraída antes de generar el documento.")
    
    data = st.session_state.extracted_data
    
    # Crear pestañas para organizar la edición
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Información Básica", "📊 Temas", "✅ Compromisos", "👥 Participantes"])
    
    edited_data = {}
    
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
        if st.button("➕ Agregar otro tema", key="add_tema"):
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
        if st.button("➕ Agregar otro compromiso", key="add_compromiso"):
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
        if st.button("➕ Agregar otro participante", key="add_participante"):
            edited_participantes.append({"nombre": "", "cargo": ""})
            st.rerun()
        
        edited_data["participantes"] = edited_participantes
    
    # Guardar datos editados
    st.session_state.edited_data = edited_data
    
    # --- SECCIÓN DE GENERACIÓN DEL DOCUMENTO ---
    st.header("3. Generación del Documento")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
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
                        type="primary",
                        key="download_button"
                    )
                    
                    st.success("✅ Documento generado exitosamente!")
                    st.info("Haz clic en el botón de arriba para descargar el archivo Word.")
                    
                except Exception as e:
                    st.error(f"❌ Error al generar el documento: {str(e)}")
                    st.error(traceback.format_exc())
    
    with col2:
        if st.button("🔄 Reiniciar Proceso", type="secondary", use_container_width=True):
            st.session_state.extracted_data = None
            st.session_state.edited_data = None
            st.rerun()

# --- SECCIÓN DE PREVISUALIZACIÓN ---
if st.session_state.edited_data:
    st.header("📋 Previsualización de Datos")
    
    with st.expander("Ver datos estructurados completos", expanded=False):
        st.json(st.session_state.edited_data)
    
    # Mostrar resumen visual
    data = st.session_state.edited_data
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📅 Fecha", data.get("fecha", "No especificada"))
        st.metric("⏰ Horario", f"{data.get('hora_inicio', '')} - {data.get('hora_fin', '')}")
    
    with col2:
        st.metric("🏙️ Ciudad", data.get("ciudad", "No especificada"))
        st.metric("📍 Sede", data.get("sede", "No especificada"))
    
    with col3:
        st.metric("📊 Temas", len(data.get("temas", [])))
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
    
    ### Solución de Problemas:
    1. Si ves errores 404, presiona "Detectar Modelos Disponibles"
    2. Asegúrate de que tu API Key tenga acceso a los modelos Gemini
    3. Verifica que tu plantilla esté en el directorio correcto
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
    
    # Información de versión
    st.divider()
    st.caption("Versión de Python: " + sys.version.split()[0])

# --- PIE DE PÁGINA ---
st.divider()
st.caption("Sistema de Automatización de Actas Clínicas | Clínica La Ermita | v1.0")
