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
Utiliza **Gemini 2.5 Flash Lite** para analizar, interpretar y completar TODOS los campos del acta.
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
            3. Asegurarte de que tenga las etiquetas correctas
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
st.info("🔬 **Modelo en uso:** Gemini 2.5 Flash Lite | Analiza, interpreta y completa TODOS los campos del acta")

# Input para la transcripción
transcription = st.text_area(
    "📝 **Transcripción de la reunión:**",
    height=200,
    placeholder="Pega aquí la transcripción completa de la reunión...",
    help="La IA analizará, interpretará y extraerá toda la información para completar el acta."
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
            # Definir el prompt COMPLETO para extracción de TODOS los campos
            prompt = f"""
            ACTÚA COMO UN ESPECIALISTA EN DOCUMENTACIÓN CLÍNICA PARA "CLÍNICA LA ERMITA DE CARTAGENA".
            
            TU TAREA: Analizar, interpretar y extraer TODA la información relevante de una transcripción de reunión clínica.
            
            INSTRUCCIONES ABSOLUTAS:
            1. Analiza DETALLADAMENTE la transcripción proporcionada
            2. Extrae TODA la información relevante para completar un acta de reunión
            3. Interpreta el contexto para inferir información cuando sea necesario
            4. Devuelve EXCLUSIVAMENTE un objeto JSON válido
            5. NO incluyas texto, explicaciones, ni markdown
            6. Si un campo no puede determinarse, usa string vacío ""
            7. Para las listas, incluye TODOS los elementos mencionados o inferidos
            
            ESTRUCTURA JSON OBLIGATORIA (EXACTA Y COMPLETA):
            {{
                "fecha": "string (formato DD/MM/YYYY)",
                "hora_inicio": "string (formato HH:MM en 24h)",
                "hora_fin": "string (formato HH:MM en 24h)",
                "ciudad": "string (ej: Cartagena)",
                "sede": "string (ej: Pie de la Popa, La Ermita)",
                "objetivo": "string (descripción completa del objetivo de la reunión)",
                "temas": [
                    {{
                        "tema": "string (título específico del tema)",
                        "desarrollo": "string (descripción detallada de lo discutido)"
                    }}
                ],
                "compromisos": [
                    {{
                        "compromiso": "string (acuerdo específico)",
                        "responsable": "string (nombre completo)",
                        "fecha": "string (fecha o plazo)"
                    }}
                ],
                "participantes": [
                    {{
                        "nombre": "string (nombre completo)",
                        "cargo": "string (cargo o función)"
                    }}
                ],
                "tema_proxima_reunion": "string (tema acordado para la próxima reunión)",
                "fecha_proxima_reunion": "string (fecha o estimación para la próxima reunión)"
            }}
            
            REGLAS ESPECÍFICAS DE EXTRACCIÓN E INTERPRETACIÓN:
            
            1. FECHA: Buscar explícitamente o inferir de contexto. Formato DD/MM/YYYY.
            2. HORAS: Buscar "a las", "desde", "hasta", "inicio", "fin". Formato HH:MM.
            3. CIUDAD/SEDE: Inferir de contexto si no se menciona explícitamente. Para Clínica La Ermita, ciudad típica es Cartagena.
            4. OBJETIVO: Extraer el propósito principal de la reunión descrito al inicio.
            5. TEMAS: Identificar CADA tema discutido con su desarrollo detallado. Incluir:
               - Presentaciones
               - Demostraciones
               - Preguntas y respuestas
               - Discusiones técnicas
               - Decisiones tomadas
            6. COMPROMISOS: Extraer TODOS los acuerdos, tareas asignadas y responsabilidades mencionadas.
            7. PARTICIPANTES: Identificar a TODOS los que hablan o son mencionados. Inferir cargos cuando sea posible.
            8. PRÓXIMA REUNIÓN: Identificar si se menciona o se infiere de contexto.
            
            CONTEXTO ESPECÍFICO PARA CLÍNICA LA ERMITA:
            - La clínica tiene sedes: Pie de la Popa, La Ermita
            - Procesos comunes: Cirugía, Hemodinamia, Concepción
            - Roles comunes: Médicos especialistas, Enfermería, Facturación, Calidad, Procesos
            
            TRANSCRIPCIÓN A ANALIZAR:
            ```text
            {transcription}
            ```
            
            IMPORTANTE: Tu análisis debe ser exhaustivo. Extrae TODA la información posible.
            Incluye al menos 3-5 temas, 2-4 compromisos, y todos los participantes mencionados.
            
            RESPUESTA REQUERIDA (SOLO JSON, NADA MÁS):
            """
            
            # Llamar a la API de Gemini
            response_text = call_gemini_api(prompt)
            
            # Procesar respuesta
            if response_text:
                try:
                    extracted_data = extract_json_from_response(response_text)
                    
                    # Validar estructura básica
                    required_keys = [
                        "fecha", "hora_inicio", "hora_fin", "ciudad", "sede", 
                        "objetivo", "temas", "compromisos", "participantes",
                        "tema_proxima_reunion", "fecha_proxima_reunion"
                    ]
                    
                    # Asegurar que todos los campos existan
                    for key in required_keys:
                        if key not in extracted_data:
                            extracted_data[key] = ""
                    
                    # Asegurar que las listas sean listas y tengan contenido mínimo
                    if not isinstance(extracted_data.get("temas"), list):
                        extracted_data["temas"] = [{"tema": "", "desarrollo": ""}]
                    elif len(extracted_data["temas"]) == 0:
                        extracted_data["temas"] = [{"tema": "Temas discutidos en la reunión", "desarrollo": "Se discutieron diversos puntos relacionados con el objetivo de la reunión."}]
                    
                    if not isinstance(extracted_data.get("compromisos"), list):
                        extracted_data["compromisos"] = [{"compromiso": "", "responsable": "", "fecha": ""}]
                    
                    if not isinstance(extracted_data.get("participantes"), list):
                        extracted_data["participantes"] = [{"nombre": "", "cargo": ""}]
                    
                    # Validar y completar ciudad/sede si están vacías
                    if not extracted_data.get("ciudad"):
                        extracted_data["ciudad"] = "Cartagena"
                    if not extracted_data.get("sede"):
                        extracted_data["sede"] = "Pie de la Popa"
                    
                    # Validar formato de fecha si existe
                    fecha = extracted_data.get("fecha", "")
                    if fecha:
                        try:
                            # Intentar parsear la fecha para validar formato
                            datetime.strptime(fecha, "%d/%m/%Y")
                        except ValueError:
                            # Si no es válida, usar fecha actual
                            extracted_data["fecha"] = datetime.now().strftime("%d/%m/%Y")
                    else:
                        # Si no hay fecha, usar fecha actual
                        extracted_data["fecha"] = datetime.now().strftime("%d/%m/%Y")
                    
                    st.session_state.extracted_data = extracted_data
                    st.session_state.edited_data = extracted_data.copy()
                    st.success("✅ Información extraída y analizada exitosamente!")
                    
                    # Mostrar vista previa detallada
                    with st.expander("📊 Vista previa completa de datos extraídos", expanded=True):
                        # Información básica
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**📅 Información General**")
                            st.info(f"**Fecha:** {extracted_data.get('fecha', 'No especificada')}")
                            st.info(f"**Horario:** {extracted_data.get('hora_inicio', '')} - {extracted_data.get('hora_fin', '')}")
                            st.info(f"**Ubicación:** {extracted_data.get('ciudad', '')} - {extracted_data.get('sede', '')}")
                        
                        with col2:
                            st.markdown("**📋 Resumen**")
                            st.info(f"**Temas identificados:** {len(extracted_data.get('temas', []))}")
                            st.info(f"**Compromisos acordados:** {len(extracted_data.get('compromisos', []))}")
                            st.info(f"**Participantes:** {len(extracted_data.get('participantes', []))}")
                        
                        # Objetivo
                        st.markdown("**🎯 Objetivo de la Reunión**")
                        st.success(extracted_data.get('objetivo', 'Objetivo no especificado'))
                        
                        # Próxima reunión
                        if extracted_data.get('tema_proxima_reunion') or extracted_data.get('fecha_proxima_reunion'):
                            st.markdown("**📅 Próxima Reunión**")
                            col_pr1, col_pr2 = st.columns(2)
                            with col_pr1:
                                st.info(f"**Tema:** {extracted_data.get('tema_proxima_reunion', 'Por definir')}")
                            with col_pr2:
                                st.info(f"**Fecha estimada:** {extracted_data.get('fecha_proxima_reunion', 'Por definir')}")
                        
                        # Vista rápida de temas
                        if extracted_data.get("temas"):
                            st.markdown("**📝 Temas Identificados**")
                            for i, tema in enumerate(extracted_data["temas"][:3], 1):  # Mostrar solo primeros 3
                                with st.expander(f"Tema {i}: {tema.get('tema', 'Sin título')[:50]}..."):
                                    st.write(tema.get('desarrollo', 'Sin desarrollo'))
                            if len(extracted_data["temas"]) > 3:
                                st.caption(f"... y {len(extracted_data['temas']) - 3} temas más")
                        
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
    st.info("Revisa y edita la información extraída. La IA ha analizado e interpretado toda la transcripción.")
    
    data = st.session_state.extracted_data
    
    # Crear pestañas para organizar la edición
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Información Básica", "📊 Temas", "✅ Compromisos", "👥 Participantes", "📅 Próxima Reunión"])
    
    edited_data = {}
    
    with tab1:
        st.markdown("**Información General de la Reunión**")
        
        col1, col2 = st.columns(2)
        with col1:
            edited_data["fecha"] = st.text_input(
                "Fecha de la Reunión (DD/MM/YYYY)", 
                value=data.get("fecha", ""),
                help="Formato: DD/MM/YYYY, ejemplo: 25/12/2024"
            )
            edited_data["hora_inicio"] = st.text_input(
                "Hora de Inicio (HH:MM)", 
                value=data.get("hora_inicio", ""),
                help="Formato 24h: HH:MM, ejemplo: 14:30"
            )
            edited_data["ciudad"] = st.text_input(
                "Ciudad", 
                value=data.get("ciudad", ""),
                placeholder="Ej: Cartagena"
            )
        
        with col2:
            edited_data["hora_fin"] = st.text_input(
                "Hora de Fin (HH:MM)", 
                value=data.get("hora_fin", ""),
                help="Formato 24h: HH:MM, ejemplo: 16:45"
            )
            edited_data["sede"] = st.text_input(
                "Sede", 
                value=data.get("sede", ""),
                placeholder="Ej: Pie de la Popa, La Ermita"
            )
        
        edited_data["objetivo"] = st.text_area(
            "Objetivo de la Reunión", 
            value=data.get("objetivo", ""),
            height=120,
            help="Descripción completa del propósito de la reunión"
        )
    
    with tab2:
        st.subheader("📊 Temas del Orden del Día")
        st.caption("Lista de temas discutidos en la reunión con sus respectivos desarrollos")
        
        # Inicializar lista de temas
        temas = data.get("temas", [])
        if not temas:
            temas = [{"tema": "", "desarrollo": ""}]
        
        edited_temas = []
        for i, tema in enumerate(temas, 1):
            st.markdown(f"**Tema {i}**")
            
            col_tema, col_des = st.columns([1, 2])
            
            with col_tema:
                nuevo_tema = st.text_input(
                    f"Título del Tema {i}", 
                    value=tema.get("tema", ""),
                    key=f"tema_{i}",
                    placeholder="Ej: Presentación de la plataforma Zipl"
                )
            
            with col_des:
                nuevo_desarrollo = st.text_area(
                    f"Desarrollo del Tema {i}",
                    value=tema.get("desarrollo", ""),
                    height=120,
                    key=f"desarrollo_{i}",
                    placeholder="Describa en detalle lo discutido sobre este tema..."
                )
            
            edited_temas.append({
                "tema": nuevo_tema,
                "desarrollo": nuevo_desarrollo
            })
            
            if i < len(temas):
                st.divider()
        
        # Botones para gestión de temas
        col_add, col_remove, col_fill = st.columns(3)
        with col_add:
            if st.button("➕ Agregar nuevo tema", key="add_tema"):
                edited_temas.append({"tema": "", "desarrollo": ""})
                st.rerun()
        
        with col_remove:
            if len(edited_temas) > 1 and st.button("➖ Eliminar último tema", key="remove_tema"):
                edited_temas.pop()
                st.rerun()
        
        with col_fill:
            if st.button("🔄 Rellenar temas automáticamente", key="fill_temas"):
                # Agregar temas genéricos si están vacíos
                for i, tema in enumerate(edited_temas):
                    if not tema.get("tema") and not tema.get("desarrollo"):
                        edited_temas[i] = {
                            "tema": f"Tema {i+1} discutido en la reunión",
                            "desarrollo": f"Se discutieron aspectos relevantes sobre este punto en la reunión."
                        }
                st.rerun()
        
        edited_data["temas"] = edited_temas
    
    with tab3:
        st.subheader("✅ Compromisos Acordados")
        st.caption("Lista de acuerdos con responsables y fechas de ejecución")
        
        # Inicializar lista de compromisos
        compromisos = data.get("compromisos", [])
        if not compromisos:
            compromisos = [{"compromiso": "", "responsable": "", "fecha": ""}]
        
        edited_compromisos = []
        for i, compromiso in enumerate(compromisos, 1):
            st.markdown(f"**Compromiso {i}**")
            
            col_comp, col_resp, col_fecha = st.columns([3, 2, 1])
            
            with col_comp:
                nuevo_compromiso = st.text_input(
                    f"Compromiso {i}",
                    value=compromiso.get("compromiso", ""),
                    key=f"compromiso_{i}",
                    placeholder="Ej: Actualizar protocolo de atención"
                )
            
            with col_resp:
                nuevo_responsable = st.text_input(
                    f"Responsable {i}",
                    value=compromiso.get("responsable", ""),
                    key=f"responsable_{i}",
                    placeholder="Nombre del responsable"
                )
            
            with col_fecha:
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
            
            if i < len(compromisos):
                st.divider()
        
        # Botones para gestión de compromisos
        col_add_c, col_remove_c, col_fill_c = st.columns(3)
        with col_add_c:
            if st.button("➕ Agregar nuevo compromiso", key="add_compromiso"):
                edited_compromisos.append({"compromiso": "", "responsable": "", "fecha": ""})
                st.rerun()
        
        with col_remove_c:
            if len(edited_compromisos) > 1 and st.button("➖ Eliminar último compromiso", key="remove_compromiso"):
                edited_compromisos.pop()
                st.rerun()
        
        with col_fill_c:
            if st.button("🔄 Rellenar compromisos", key="fill_compromisos"):
                for i, comp in enumerate(edited_compromisos):
                    if not comp.get("compromiso"):
                        edited_compromisos[i]["compromiso"] = f"Compromiso {i+1} acordado en reunión"
                    if not comp.get("responsable"):
                        edited_compromisos[i]["responsable"] = "Por asignar"
                    if not comp.get("fecha"):
                        edited_compromisos[i]["fecha"] = "Por definir"
                st.rerun()
        
        edited_data["compromisos"] = edited_compromisos
    
    with tab4:
        st.subheader("👥 Participantes")
        st.caption("Lista de asistentes a la reunión con sus cargos")
        
        # Inicializar lista de participantes
        participantes = data.get("participantes", [])
        if not participantes:
            participantes = [{"nombre": "", "cargo": ""}]
        
        edited_participantes = []
        for i, participante in enumerate(participantes, 1):
            st.markdown(f"**Participante {i}**")
            
            col_nombre, col_cargo = st.columns(2)
            
            with col_nombre:
                nuevo_nombre = st.text_input(
                    f"Nombre {i}",
                    value=participante.get("nombre", ""),
                    key=f"nombre_{i}",
                    placeholder="Nombre completo"
                )
            
            with col_cargo:
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
            
            if i < len(participantes):
                st.divider()
        
        # Botones para gestión de participantes
        col_add_p, col_remove_p, col_fill_p = st.columns(3)
        with col_add_p:
            if st.button("➕ Agregar nuevo participante", key="add_participante"):
                edited_participantes.append({"nombre": "", "cargo": ""})
                st.rerun()
        
        with col_remove_p:
            if len(edited_participantes) > 1 and st.button("➖ Eliminar último participante", key="remove_participante"):
                edited_participantes.pop()
                st.rerun()
        
        with col_fill_p:
            if st.button("🔄 Rellenar participantes", key="fill_participantes"):
                # Agregar participantes comunes si están vacíos
                participantes_comunes = [
                    {"nombre": "Coordinador de Calidad", "cargo": "Profesional de Procesos"},
                    {"nombre": "Jefe de Enfermería", "cargo": "Coordinación General de Enfermería"},
                    {"nombre": "Médico Especialista", "cargo": "Coordinación Médica"}
                ]
                
                for i, part in enumerate(edited_participantes):
                    if not part.get("nombre"):
                        if i < len(participantes_comunes):
                            edited_participantes[i] = participantes_comunes[i]
                        else:
                            edited_participantes[i]["nombre"] = f"Participante {i+1}"
                            edited_participantes[i]["cargo"] = "Por definir"
                st.rerun()
        
        edited_data["participantes"] = edited_participantes
    
    with tab5:
        st.subheader("📅 Próxima Reunión")
        st.caption("Información sobre la próxima reunión planificada")
        
        col_tema_pr, col_fecha_pr = st.columns(2)
        
        with col_tema_pr:
            edited_data["tema_proxima_reunion"] = st.text_input(
                "Tema de la Próxima Reunión",
                value=data.get("tema_proxima_reunion", ""),
                placeholder="Ej: Seguimiento de implementación de Zipl"
            )
        
        with col_fecha_pr:
            edited_data["fecha_proxima_reunion"] = st.text_input(
                "Fecha de la Próxima Reunión",
                value=data.get("fecha_proxima_reunion", ""),
                placeholder="Ej: 15/12/2024 o 'Próxima semana'"
            )
    
    # Guardar datos editados
    st.session_state.edited_data = edited_data
    
    # --- SECCIÓN DE GENERACIÓN DEL DOCUMENTO ---
    st.header("3. Generación del Acta Completa")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("📄 Generar Acta Completa en Word", type="primary", use_container_width=True):
            if not validate_api_key():
                st.stop()
            
            template_content = load_template()
            if template_content is None:
                st.stop()
            
            with st.spinner("🔄 Generando documento Word con TODOS los campos..."):
                try:
                    # Importar docxtpl solo cuando sea necesario
                    from docxtpl import DocxTemplate
                    
                    # Guardar datos editados
                    final_data = st.session_state.edited_data
                    
                    # Preparar contexto COMPLETO para la plantilla
                    context = {
                        # Campos básicos
                        "FECHA": final_data.get("fecha", ""),
                        "HORA_INICIO": final_data.get("hora_inicio", ""),
                        "HORA_FIN": final_data.get("hora_fin", ""),
                        "CIUDAD": final_data.get("ciudad", ""),
                        "SEDE": final_data.get("sede", ""),
                        "OBJETIVO_DE_LA_REUNION": final_data.get("objetivo", ""),
                        
                        # Tablas dinámicas
                        "temas": final_data.get("temas", []),
                        "compromisos": final_data.get("compromisos", []),
                        "participantes": final_data.get("participantes", []),
                        
                        # Próxima reunión
                        "TEMA_PROXIMA_REUNION": final_data.get("tema_proxima_reunion", ""),
                        "FECHA_PROXIMA_REUNION": final_data.get("fecha_proxima_reunion", ""),
                    }
                    
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
                    filename = f"ACTA_CLINICA_COMPLETA_{fecha_actual}.docx"
                    
                    # Mostrar información del documento
                    st.success("✅ ¡Acta generada exitosamente con TODOS los campos!")
                    
                    # Mostrar resumen de lo que se incluyó
                    with st.expander("📋 Resumen del contenido generado", expanded=True):
                        st.info(f"**📅 Fecha de reunión:** {final_data.get('fecha', 'No especificada')}")
                        st.info(f"**🎯 Objetivo:** {final_data.get('objetivo', 'No especificado')[:100]}...")
                        st.info(f"**📊 Temas incluidos:** {len(final_data.get('temas', []))}")
                        st.info(f"**✅ Compromisos:** {len(final_data.get('compromisos', []))}")
                        st.info(f"**👥 Participantes:** {len(final_data.get('participantes', []))}")
                        st.info(f"**📅 Próxima reunión:** {final_data.get('tema_proxima_reunion', 'No definida')}")
                    
                    # Botón de descarga
                    st.download_button(
                        label="⬇️ Descargar Acta Completa",
                        data=output_stream,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        type="primary",
                        key="download_button"
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error al generar el documento: {str(e)}")
                    st.error(traceback.format_exc())
    
    with col2:
        if st.button("🔄 Actualizar Vista Previa", type="secondary", use_container_width=True):
            st.rerun()
    
    with col3:
        if st.button("🔄 Reiniciar Todo", type="secondary", use_container_width=True):
            st.session_state.extracted_data = None
            st.session_state.edited_data = None
            st.rerun()

# --- SECCIÓN DE PREVISUALIZACIÓN ---
if st.session_state.edited_data:
    st.header("📋 Vista Previa Completa del Acta")
    
    with st.expander("📊 Ver todos los datos estructurados", expanded=False):
        st.json(st.session_state.edited_data)
    
    # Mostrar resumen visual completo
    data = st.session_state.edited_data
    
    st.subheader("📋 Resumen Final del Acta")
    
    # Primera fila de métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📅 Fecha", data.get("fecha", "No especificada") or "No especificada")
    
    with col2:
        horario = f"{data.get('hora_inicio', '')} - {data.get('hora_fin', '')}"
        st.metric("⏰ Horario", horario if horario != " - " else "No especificado")
    
    with col3:
        ubicacion = f"{data.get('ciudad', '')} - {data.get('sede', '')}"
        st.metric("📍 Ubicación", ubicacion if ubicacion != " - " else "No especificada")
    
    with col4:
        st.metric("🎯 Objetivo", "Definido" if data.get("objetivo") else "No definido")
    
    # Segunda fila de métricas
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric("📊 Temas", len(data.get("temas", [])))
    
    with col6:
        st.metric("✅ Compromisos", len(data.get("compromisos", [])))
    
    with col7:
        st.metric("👥 Participantes", len(data.get("participantes", [])))
    
    with col8:
        tiene_proxima = "Sí" if data.get("tema_proxima_reunion") else "No"
        st.metric("📅 Próxima reunión", tiene_proxima)

# --- INSTRUCCIONES EN EL SIDEBAR ---
with st.sidebar:
    st.header("ℹ️ Instrucciones")
    
    st.markdown("""
    ### 🚀 Flujo Completo:
    1. **📝 Pega** la transcripción completa
    2. **🤖 La IA analiza, interpreta y extrae TODO**
    3. **✏️ Revisa y edita** los datos extraídos
    4. **📄 Genera** el documento Word completo
    5. **⬇️ Descarga** el acta lista
    
    ### ⚙️ ¿Qué extrae la IA?
    **TODOS los campos del acta:**
    - 📅 Fecha, horas, ciudad, sede
    - 🎯 Objetivo completo
    - 📊 Temas con desarrollo detallado
    - ✅ Compromisos con responsables
    - 👥 Participantes con cargos
    - 📅 Próxima reunión (tema y fecha)
    
    ### 🎯 Modelo en uso:
    **Gemini 2.5 Flash Lite**
    - Analiza contexto profundamente
    - Interpreta información implícita
    - Completa TODOS los campos
    - Alta precisión en extracción
    
    ### 📋 Campos del Acta:
    - `{{FECHA}}`, `{{HORA_INICIO}}`, `{{HORA_FIN}}`
    - `{{CIUDAD}}`, `{{SEDE}}`
    - `{{OBJETIVO_DE_LA_REUNION}}`
    - Tablas: `{{tema}}`, `{{desarrollo}}`
    - Tablas: `{{compromiso}}`, `{{responsable}}`, `{{fecha}}`
    - Tablas: `{{nombre}}`, `{{cargo}}`
    - `{{TEMA_PROXIMA_REUNION}}`, `{{FECHA_PROXIMA_REUNION}}`
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
    st.caption("**Versión:** 3.0 | **Modelo:** Gemini 2.5 Flash Lite")
    st.caption("**Capacidad:** Extracción completa de actas")
    st.caption(f"**Fecha:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# --- PIE DE PÁGINA ---
st.divider()
st.caption("🏥 Sistema Completo de Automatización de Actas Clínicas | Clínica La Ermita de Cartagena | v3.0 | Powered by Gemini 2.5 Flash Lite")
