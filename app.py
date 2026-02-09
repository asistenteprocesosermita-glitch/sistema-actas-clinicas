import streamlit as st
import json
import io
import os
import requests
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
Utiliza **Gemini 2.5 Flash Lite** para extraer información y genera documentos Word con formato profesional.
""")

# Inicialización de variables en session_state
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None
if 'edited_data' not in st.session_state:
    st.session_state.edited_data = None
if 'template_content' not in st.session_state:
    st.session_state.template_content = None

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

def call_gemini_api(prompt: str) -> str:
    """Llama a la API de Gemini 2.5 Flash Lite usando requests directamente"""
    api_key = st.secrets["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Extraer el texto de la respuesta
        if "candidates" in result and len(result["candidates"]) > 0:
            if "content" in result["candidates"][0]:
                return result["candidates"][0]["content"]["parts"][0]["text"]
        
        raise ValueError("Respuesta de la API no tiene el formato esperado")
        
    except requests.exceptions.Timeout:
        raise Exception("Timeout: La API no respondió en 30 segundos")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error en la solicitud HTTP: {str(e)}")
    except Exception as e:
        raise Exception(f"Error al procesar la respuesta: {str(e)}")

# --- SECCIÓN DE EXTRACCIÓN CON IA ---
st.header("1. Extracción de Información con IA")

# Mostrar información del modelo
st.info("🔬 **Modelo en uso:** Gemini 2.5 Flash Lite | Versión más reciente y optimizada")

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
    
    with st.spinner("🤖 Analizando transcripción con Gemini 2.5 Flash Lite..."):
        try:
            # Definir el prompt estricto para extracción
            prompt = f"""
            ACTÚA COMO UN ESPECIALISTA EN DOCUMENTACIÓN CLÍNICA.
            
            TU TAREA: Extraer información estructurada de una transcripción de reunión clínica.
            
            INSTRUCCIONES ABSOLUTAS:
            1. Analiza SOLO la transcripción proporcionada
            2. Extrae SOLO los datos solicitados
            3. Devuelve EXCLUSIVAMENTE un objeto JSON válido
            4. NO incluyas texto, explicaciones, ni markdown
            5. NO añadas comentarios ni notas
            6. Si un campo no puede determinarse, usa string vacío ""
            
            ESTRUCTURA JSON OBLIGATORIA (EXACTA):
            {{
                "fecha": "string (formato DD/MM/YYYY)",
                "hora_inicio": "string (formato HH:MM en 24h)",
                "hora_fin": "string (formato HH:MM en 24h)",
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
            
            REGLAS ESPECÍFICAS DE EXTRACCIÓN:
            1. FECHA: Buscar en la transcripción. Formato DD/MM/YYYY. Si no se encuentra, usar ""
            2. HORA: Buscar patrones como "a las", "desde", "hasta", "de". Formato 24h HH:MM
            3. CIUDAD/SEDE: Extraer nombres completos. Ej: "Cartagena", "Sede Principal"
            4. OBJETIVO: Una frase clara y concisa del propósito principal de la reunión
            5. TEMAS: Cada punto discutido en la reunión con su desarrollo detallado
            6. COMPROMISOS: Acuerdos específicos con responsables claros y fechas estimadas
            7. PARTICIPANTES: Lista completa con nombres y cargos/títulos
            
            TRANSCRIPCIÓN A ANALIZAR:
            ```text
            {transcription}
            ```
            
            RESPUESTA REQUERIDA (SOLO JSON, NADA MÁS):
            """
            
            # Llamar a la API de Gemini
            response_text = call_gemini_api(prompt)
            
            # Procesar respuesta
            if response_text:
                try:
                    extracted_data = extract_json_from_response(response_text)
                    
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
                    
                    # Validar formato de fecha si existe
                    fecha = extracted_data.get("fecha", "")
                    if fecha:
                        try:
                            # Intentar parsear la fecha para validar formato
                            datetime.strptime(fecha, "%d/%m/%Y")
                        except ValueError:
                            st.warning(f"⚠️ La fecha '{fecha}' no tiene el formato DD/MM/YYYY. Por favor, corrige en la siguiente sección.")
                    
                    st.session_state.extracted_data = extracted_data
                    st.session_state.edited_data = extracted_data.copy()
                    st.success("✅ Información extraída exitosamente con Gemini 2.5 Flash Lite!")
                    
                    # Mostrar vista previa
                    with st.expander("📊 Vista previa de datos extraídos", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("📅 Fecha", extracted_data.get("fecha", "No especificada"))
                            st.metric("⏰ Horario", f"{extracted_data.get('hora_inicio', '')} - {extracted_data.get('hora_fin', '')}")
                        with col2:
                            st.metric("🏙️ Ciudad", extracted_data.get("ciudad", "No especificada"))
                            st.metric("📍 Sede", extracted_data.get("sede", "No especificada"))
                        
                        st.markdown(f"**🎯 Objetivo:** {extracted_data.get('objetivo', '')}")
                        
                        # Mostrar resumen de conteos
                        col3, col4, col5 = st.columns(3)
                        with col3:
                            st.metric("📊 Temas", len(extracted_data.get("temas", [])))
                        with col4:
                            st.metric("✅ Compromisos", len(extracted_data.get("compromisos", [])))
                        with col5:
                            st.metric("👥 Participantes", len(extracted_data.get("participantes", [])))
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar la respuesta de la IA: {str(e)}")
                    st.error("La IA no devolvió un JSON válido.")
                    st.code(response_text[:500] + "..." if len(response_text) > 500 else response_text, language="json")
            else:
                st.error("❌ La IA no devolvió ninguna respuesta")
                
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                st.error("❌ Error 404: Modelo Gemini 2.5 Flash Lite no encontrado")
                st.info("""
                Posibles soluciones:
                1. Verifica que tengas acceso al modelo Gemini 2.5 Flash Lite
                2. Asegúrate de que tu API Key sea válida
                3. Intenta con otro modelo (gemini-2.0-flash o gemini-1.5-flash)
                4. Revisa la documentación de Google AI Studio
                """)
            elif "timeout" in error_msg.lower():
                st.error("❌ Timeout: La API tardó demasiado en responder")
                st.info("Intenta nuevamente o reduce la longitud de la transcripción.")
            else:
                st.error(f"❌ Error al comunicarse con la IA: {error_msg}")
            
            st.code(traceback.format_exc(), language="python")

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
            edited_data["fecha"] = st.text_input(
                "Fecha (DD/MM/YYYY)", 
                value=data.get("fecha", ""),
                help="Formato: DD/MM/YYYY, ejemplo: 25/12/2024"
            )
            edited_data["hora_inicio"] = st.text_input(
                "Hora de Inicio (HH:MM)", 
                value=data.get("hora_inicio", ""),
                help="Formato 24h: HH:MM, ejemplo: 14:30"
            )
            edited_data["ciudad"] = st.text_input("Ciudad", value=data.get("ciudad", ""))
        
        with col2:
            edited_data["hora_fin"] = st.text_input(
                "Hora de Fin (HH:MM)", 
                value=data.get("hora_fin", ""),
                help="Formato 24h: HH:MM, ejemplo: 16:45"
            )
            edited_data["sede"] = st.text_input("Sede", value=data.get("sede", ""))
        
        edited_data["objetivo"] = st.text_area(
            "Objetivo de la Reunión", 
            value=data.get("objetivo", ""),
            height=100,
            help="Descripción clara del propósito de la reunión"
        )
    
    with tab2:
        st.subheader("Temas del Orden del Día")
        st.caption("Lista de temas discutidos en la reunión con sus respectivos desarrollos")
        
        # Inicializar lista de temas si no existe
        temas = data.get("temas", [])
        if not temas:
            temas = [{"tema": "", "desarrollo": ""}]
        
        edited_temas = []
        for i, tema in enumerate(temas, 1):
            st.markdown(f"**Tema {i}**")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                nuevo_tema = st.text_input(
                    f"Título del Tema {i}", 
                    value=tema.get("tema", ""),
                    key=f"tema_{i}",
                    placeholder="Ej: Revisión de indicadores de calidad"
                )
            
            with col2:
                nuevo_desarrollo = st.text_area(
                    f"Desarrollo del Tema {i}",
                    value=tema.get("desarrollo", ""),
                    height=100,
                    key=f"desarrollo_{i}",
                    placeholder="Describa en detalle lo discutido sobre este tema..."
                )
            
            edited_temas.append({
                "tema": nuevo_tema,
                "desarrollo": nuevo_desarrollo
            })
            
            st.divider()
        
        # Botones para gestión de temas
        col_add, col_remove = st.columns(2)
        with col_add:
            if st.button("➕ Agregar nuevo tema", key="add_tema"):
                edited_temas.append({"tema": "", "desarrollo": ""})
                st.rerun()
        
        with col_remove:
            if len(edited_temas) > 1 and st.button("➖ Eliminar último tema", key="remove_tema"):
                edited_temas.pop()
                st.rerun()
        
        edited_data["temas"] = edited_temas
    
    with tab3:
        st.subheader("Compromisos Acordados")
        st.caption("Lista de acuerdos con responsables y fechas de ejecución")
        
        # Inicializar lista de compromisos si no existe
        compromisos = data.get("compromisos", [])
        if not compromisos:
            compromisos = [{"compromiso": "", "responsable": "", "fecha": ""}]
        
        edited_compromisos = []
        for i, compromiso in enumerate(compromisos, 1):
            st.markdown(f"**Compromiso {i}**")
            
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                nuevo_compromiso = st.text_input(
                    f"Compromiso {i}",
                    value=compromiso.get("compromiso", ""),
                    key=f"compromiso_{i}",
                    placeholder="Ej: Actualizar protocolo de atención"
                )
            
            with col2:
                nuevo_responsable = st.text_input(
                    f"Responsable {i}",
                    value=compromiso.get("responsable", ""),
                    key=f"responsable_{i}",
                    placeholder="Nombre del responsable"
                )
            
            with col3:
                nuevo_fecha = st.text_input(
                    f"Fecha {i}",
                    value=compromiso.get("fecha", ""),
                    key=f"fecha_comp_{i}",
                    placeholder="DD/MM/YYYY"
                )
            
            edited_compromisos.append({
                "compromiso": nuevo_compromiso,
                "responsable": nuevo_responsable,
                "fecha": nuevo_fecha
            })
            
            st.divider()
        
        # Botones para gestión de compromisos
        col_add_c, col_remove_c = st.columns(2)
        with col_add_c:
            if st.button("➕ Agregar nuevo compromiso", key="add_compromiso"):
                edited_compromisos.append({"compromiso": "", "responsable": "", "fecha": ""})
                st.rerun()
        
        with col_remove_c:
            if len(edited_compromisos) > 1 and st.button("➖ Eliminar último compromiso", key="remove_compromiso"):
                edited_compromisos.pop()
                st.rerun()
        
        edited_data["compromisos"] = edited_compromisos
    
    with tab4:
        st.subheader("Participantes")
        st.caption("Lista de asistentes a la reunión con sus cargos")
        
        # Inicializar lista de participantes si no existe
        participantes = data.get("participantes", [])
        if not participantes:
            participantes = [{"nombre": "", "cargo": ""}]
        
        edited_participantes = []
        for i, participante in enumerate(participantes, 1):
            st.markdown(f"**Participante {i}**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_nombre = st.text_input(
                    f"Nombre {i}",
                    value=participante.get("nombre", ""),
                    key=f"nombre_{i}",
                    placeholder="Nombre completo"
                )
            
            with col2:
                nuevo_cargo = st.text_input(
                    f"Cargo {i}",
                    value=participante.get("cargo", ""),
                    key=f"cargo_{i}",
                    placeholder="Cargo o posición"
                )
            
            edited_participantes.append({
                "nombre": nuevo_nombre,
                "cargo": nuevo_cargo
            })
            
            st.divider()
        
        # Botones para gestión de participantes
        col_add_p, col_remove_p = st.columns(2)
        with col_add_p:
            if st.button("➕ Agregar nuevo participante", key="add_participante"):
                edited_participantes.append({"nombre": "", "cargo": ""})
                st.rerun()
        
        with col_remove_p:
            if len(edited_participantes) > 1 and st.button("➖ Eliminar último participante", key="remove_participante"):
                edited_participantes.pop()
                st.rerun()
        
        edited_data["participantes"] = edited_participantes
    
    # Guardar datos editados
    st.session_state.edited_data = edited_data
    
    # --- SECCIÓN DE GENERACIÓN DEL DOCUMENTO ---
    st.header("3. Generación del Documento Word")
    
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
                    
                    # Mostrar información del documento
                    st.success("✅ Documento generado exitosamente!")
                    
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
                    
                    # Mostrar información del documento generado
                    st.info(f"""
                    **📋 Información del documento generado:**
                    - 📄 Nombre: {filename}
                    - 📊 Temas incluidos: {len(final_data.get("temas", []))}
                    - ✅ Compromisos: {len(final_data.get("compromisos", []))}
                    - 👥 Participantes: {len(final_data.get("participantes", []))}
                    """)
                    
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
    
    with st.expander("📊 Ver datos estructurados completos", expanded=False):
        st.json(st.session_state.edited_data)
    
    # Mostrar resumen visual
    data = st.session_state.edited_data
    
    st.subheader("Resumen del Acta")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📅 Fecha", data.get("fecha", "No especificada") or "No especificada")
    
    with col2:
        horario = f"{data.get('hora_inicio', '')} - {data.get('hora_fin', '')}"
        st.metric("⏰ Horario", horario if horario != " - " else "No especificado")
    
    with col3:
        st.metric("📍 Ubicación", f"{data.get('ciudad', '')} - {data.get('sede', '')}" 
                 if data.get('ciudad') or data.get('sede') else "No especificada")
    
    with col4:
        st.metric("🎯 Objetivo", "Definido" if data.get("objetivo") else "No definido")

# --- INSTRUCCIONES EN EL SIDEBAR ---
with st.sidebar:
    st.header("ℹ️ Instrucciones")
    
    st.markdown("""
    ### 🚀 Flujo de Trabajo:
    1. **📝 Pega** la transcripción de la reunión
    2. **🤖 Haz clic** en "Extraer Información con IA"
    3. **✏️ Revisa y edita** los datos extraídos
    4. **📄 Genera** el documento Word
    5. **⬇️ Descarga** el acta lista
    
    ### ⚙️ Requisitos:
    • 🔑 API Key de Gemini configurada en secrets
    • 📄 Plantilla Word en el directorio de la app
    • 🗣️ Transcripción lo más completa posible
    
    ### 🎯 Modelo en uso:
    **Gemini 2.5 Flash Lite**
    - Última versión disponible
    - Optimizado para velocidad
    - Alta precisión en extracción
    - Soporte JSON nativo
    
    ### 📋 Etiquetas de la Plantilla:
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
    
    # Información de la aplicación
    st.divider()
    st.caption("**Versión:** 2.5 | **Modelo:** Gemini 2.5 Flash Lite")
    st.caption("**Última actualización:** " + datetime.now().strftime("%d/%m/%Y"))

# --- PIE DE PÁGINA ---
st.divider()
st.caption("🏥 Sistema de Automatización de Actas Clínicas | Clínica La Ermita | v2.5 | Powered by Gemini 2.5 Flash Lite")
