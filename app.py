import re
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

cursos_disponibles = [
    "Python 10-12",
    "Roblox 8-9",
    "Roblox 10-12",
    "Minecraft Level 1",
    "Minecraft Level 2",
    "Digital Creativity Level 1",
    "Digital Creativity Level 2",
]

# ----------------------------------
# CONFIG
# ----------------------------------

st.set_page_config(
    page_title="GCC Leveling Dashboard",
    layout="wide"
)

st.title("🚀GCC Leveling Dashboard")

# ----------------------------------
# GOOGLE SHEETS
# ----------------------------------

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scopes
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1IlH8DKJ02yWh40ww9xFf3RlZ5dMOFMF8OHwDzWwplGs/edit"
)

@st.cache_data(show_spinner=False, ttl=30)
def leer_hoja_valores(title):
    ws = spreadsheet.worksheet(title)
    return ws.get_all_values()


@st.cache_data(show_spinner=False, ttl=30)
def leer_hoja_registros(title):
    ws = spreadsheet.worksheet(title)
    return ws.get_all_records()


def limpiar_cache_hojas():
    st.cache_data.clear()


def get_or_create_worksheet(title, headers=None):
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=title,
            rows="1000",
            cols="20"
        )
        if headers:
            ws.append_row(headers)
    return ws

worksheet = get_or_create_worksheet(
    "LEVELING_REQUESTS",
    headers=[
        "Fecha",
        "ID",
        "Estudiante",
        "Edad",
        "Backoffice",
        "Graduado",
        "Curso",
        "Solicitud",
        "Estado",
        "Creado por",
        "Observaciones",
        "TL",
        "Tutor",
        "Mensaje"
    ]
)

worksheet_extras = get_or_create_worksheet(
    "EXTRA_REQUESTS",
    headers=[
        "Fecha",
        "ID",
        "Backoffice del Estudiante",
        "Backoffice del grupo",
        "Tiempo de la clase extra",
        "Curso",
        "Clases a recuperar",
        "Tipo de clase extra",
        "Observaciones",
        "Creado por:",
        "TL",
        "Tutor",
        "Mensaje",
        "Enviado a Slack"
    ]
)

# ----------------------------------
# GENERAR ID
# ----------------------------------

def generar_id(sheet):

    data = leer_hoja_valores(sheet.title)

    ids = []

    for fila in data[1:]:

        try:
            ids.append(int(str(fila[1]).strip()))
        except:
            pass

    # Si aún no hay solicitudes,
    # empezar desde la 1
    if not ids:
        return "1"

    ultimo = max(ids)

    # El siguiente ID es el mayor actual + 1
    if ultimo < 1:
        return "1"

    return str(ultimo + 1)

# ----------------------------------
# EXTRAER CODIGO 
# ----------------------------------
def extraer_codigo_bo(valor):

    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    valor = valor.split("#")[0]

    return valor.rstrip("/").split("/")[-1]

def limpiar_columnas(columnas):

    nuevas = []
    contador = {}

    for col in columnas:

        col = str(col).strip()

        if col == "":
            col = "col_vacia"

        if col in contador:
            contador[col] += 1
            col = f"{col}_{contador[col]}"
        else:
            contador[col] = 0

        nuevas.append(col)

    return nuevas


def cargar_solicitudes(sheet):
    data = leer_hoja_valores(sheet.title)

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(
        data[1:],
        columns=data[0]
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    df = df.replace(
        r'^\s*$',
        pd.NA,
        regex=True
    ).dropna(how="all")

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(
            df["Fecha"],
            errors="coerce"
        )

    if "Estado" not in df.columns:
        df["Estado"] = "Open"
    else:
        df["Estado"] = df["Estado"].apply(normalize_status)

    return df


def get_estado(row):
    if "Estado" in row.index:
        estado = str(row.get("Estado", "")).strip()
        if estado:
            return estado
    return "Open"


def normalize_status(value):
    if pd.isna(value):
        return "Open"

    status = str(value).strip().lower()
    if status in {"open", "abierto", "opened"}:
        return "Open"
    if status in {"pending", "pendiente", "pending review", "pendiente review"}:
        return "Pending"
    return str(value).strip() or "Open"


def limpiar_texto(valor):
    return str(valor or "").strip().lower()


def normalizar_curso(valor):
    if pd.isna(valor):
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(valor).strip().lower()).strip()


def inferir_curso_desde_texto(texto):
    if not texto:
        return None

    texto_normalizado = normalizar_curso(texto)

    if not texto_normalizado:
        return None

    patrones = {
        "Digital Creativity Level 1": [
            "digital creativity level 1",
            "digital creativity level1",
            "dc level 1",
            "dc level1",
            "digital creativity 1",
        ],
        "Digital Creativity 8-9": [
            "digital creativity 8 9",
            "digital creativity 8-9",
            "digital creativity 8 to 9",
        ],
        "Digital Creativity 10-12": [
            "digital creativity 10 12",
            "digital creativity 10-12",
            "digital creativity 10 to 12",
        ],
        "Minecraft Level 1": [
            "minecraft level 1",
            "minecraft level1",
        ],
        "Minecraft Level 2": [
            "minecraft level 2",
            "minecraft level2",
        ],
        "Python 10-12": [
            "python 10 12",
            "python 10-12",
            "python 10 to 12",
        ],
        "Roblox 8-9": [
            "roblox 8 9",
            "roblox 8-9",
            "roblox 8 to 9",
        ],
        "Roblox 10-12": [
            "roblox 10 12",
            "roblox 10-12",
            "roblox 10 to 12",
        ],
    }

    for curso, patrones_curso in patrones.items():
        if any(patron in texto_normalizado for patron in patrones_curso):
            return curso

    return None


def inferir_curso_desde_grupo(nombre_grupo):
    if not nombre_grupo:
        return None

    nombre = str(nombre_grupo).strip().upper()

    match_codigo = re.search(r'GCC\s*(RO|PY|ME|DC)', nombre)
    if not match_codigo:
        return None

    codigo = match_codigo.group(1)

    match_edad = re.search(r'\((\d+[\s-]+\d+)\s*[^)]*\)', nombre)
    if not match_edad:
        return None

    edad_raw = re.sub(r'\s+', '-', match_edad.group(1).strip())

    mapeo_codigos = {
        "RO": "Roblox",
        "PY": "Python",
        "ME": "Minecraft",
        "DC": "Digital Creativity",
    }

    materia = mapeo_codigos[codigo]

    if materia in ("Roblox", "Python"):
        curso = f"{materia} {edad_raw}"
        if curso in cursos_disponibles:
            return curso
        return None

    nums = re.findall(r'\d+', edad_raw)
    if nums:
        primer_num = int(nums[0])
        nivel = "Level 1" if primer_num <= 12 else "Level 2"
        curso = f"{materia} {nivel}"
        if curso in cursos_disponibles:
            return curso

    return None


def obtener_tutor_por_grupo(grupo_backoffice, spreadsheet):
    try:
        groups_data = leer_hoja_valores("Groups & Tutors")
    except Exception:
        return "", None

    if not groups_data:
        return "", None

    groups_df = pd.DataFrame(groups_data[1:], columns=groups_data[0])
    groups_df.columns = groups_df.columns.astype(str).str.strip()

    grupo_backoffice = str(grupo_backoffice or "").strip()
    if not grupo_backoffice:
        return "", None

    grupo_normalizado = limpiar_texto(grupo_backoffice)

    for _, fila in groups_df.iterrows():
        nombre_grupo = str(fila.iloc[0] or "").strip()
        if not nombre_grupo:
            continue

        nombre_grupo_normalizado = limpiar_texto(nombre_grupo)
        if (
            nombre_grupo_normalizado == grupo_normalizado
            or grupo_normalizado in nombre_grupo_normalizado
        ):
            tutor = str(fila.iloc[1] or "").strip()
            return tutor, fila

    return "", None


def obtener_tutores_disponibles(curso_solicitado, spreadsheet):
    try:
        tts_data = leer_hoja_registros("TTS")
    except Exception:
        return pd.DataFrame(columns=["Name", "Casos"])

    if not tts_data:
        return pd.DataFrame(columns=["Name", "Casos"])

    tts_df = pd.DataFrame(tts_data)
    tts_df.columns = tts_df.columns.astype(str).str.strip()

    columna_curso = curso_solicitado
    if columna_curso not in tts_df.columns:
        columna_curso = next(
            (
                columna
                for columna in tts_df.columns
                if normalizar_curso(columna) and normalizar_curso(columna) in normalizar_curso(curso_solicitado)
            ),
            None
        )

    if not columna_curso or columna_curso not in tts_df.columns:
        return pd.DataFrame(columns=["Name", "Casos"])

    tutores_curso = tts_df[
        (
            tts_df["Status"]
            .astype(str)
            .str.strip()
            .str.lower()
            == "active"
        )
        &
        (
            tts_df[columna_curso]
            .astype(str)
            .str.strip()
            .str.upper()
            == "TRUE"
        )
    ].copy()

    if tutores_curso.empty:
        return pd.DataFrame(columns=["Name", "Casos"])

    carga_real = {}
    try:
        carga_real = calcular_carga_real(spreadsheet)
    except Exception:
        carga_real = {}

    tutores_curso["Casos"] = (
        tutores_curso["Name"]
        .astype(str)
        .str.strip()
        .map(lambda x: int(carga_real.get(x, 0)))
    )

    return tutores_curso.sort_values("Casos")


def calcular_carga_real(spreadsheet):

    carga = {}

    # ----------------------------------
    # RESPUESTAS (casos cerrados)
    # ----------------------------------

    respuestas_data = leer_hoja_valores("respuestas")

    respuestas_df = pd.DataFrame(
        respuestas_data[1:],
        columns=respuestas_data[0]
    )

    respuestas_df.columns = (
        respuestas_df.columns
        .astype(str)
        .str.strip()
    )

    ids_cerrados = set(
        respuestas_df[
            "ID de la solicitud que te hicieron (OJO Está en el hilo de slack donde fuiste asignado)"
        ]
        .astype(str)
        .str.strip()
    )

    # ----------------------------------
    # LEVELING REQUESTS
    # ----------------------------------

    data = worksheet.get_all_values()

    df = pd.DataFrame(
        data[1:],
        columns=data[0]
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    pendientes_leveling = df[
        ~df["ID"]
        .astype(str)
        .str.strip()
        .isin(ids_cerrados)
    ]

    for _, fila in pendientes_leveling.iterrows():

        tutor = str(
            fila.get("Tutor", "")
        ).strip()

        if tutor:

            carga[tutor] = (
                carga.get(tutor, 0) + 1
            )

    # ----------------------------------
    # RESPUESTAS GRADUADOS
    # ----------------------------------

    grad_data = leer_hoja_valores("respuestas - graduados")

    grad_df = pd.DataFrame(
        grad_data[1:],
        columns=grad_data[0]
    )

    grad_df.columns = limpiar_columnas(
        grad_df.columns
    )

    bos_cerrados = set(
        grad_df["BO del estudiante"]
        .apply(extraer_codigo_bo)
    )

    # ----------------------------------
    # TLA
    # ----------------------------------

    tla_data = leer_hoja_valores("CS")

    tla_df = pd.DataFrame(
        tla_data[1:],
        columns=tla_data[0]
    )

    tla_df.columns = limpiar_columnas(
        tla_df.columns
    )

    tla_df["codigo_bo"] = (
        tla_df[
            "Link al Back Office del estudiante"
        ]
        .apply(extraer_codigo_bo)
    )

    pendientes_tla = tla_df[
        ~tla_df["codigo_bo"]
        .isin(bos_cerrados)
    ]

    for _, fila in pendientes_tla.iterrows():

        tutor = str(
            fila.get("Tutor", "")
        ).strip()

        if tutor:

            carga[tutor] = (
                carga.get(tutor, 0) + 1
            )

    return carga

# ----------------------------------
# MENÚ
# ----------------------------------

menu = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Home",
        "📝 New Request",
        "📋 View Requests",
        "🔎 Search Case",
        "📊 Metrics"
    ]
)
# ----------------------------------
# INICIO
# ----------------------------------

if menu == "🏠 Home":

    st.header("🏠 Operational Summary")

    frames = []

    leveling_df = cargar_solicitudes(worksheet).copy()
    if not leveling_df.empty:
        leveling_df["Tipo de solicitud"] = "Leveling"
        frames.append(leveling_df)

    extras_df = cargar_solicitudes(worksheet_extras).copy()
    if not extras_df.empty:
        extras_df["Tipo de solicitud"] = "Extra Class"
        frames.append(extras_df)

    if not frames:
        st.info("There are no registered requests")
        st.stop()

    df = pd.concat(frames, ignore_index=True)
    df.columns = df.columns.astype(str).str.strip()

    if "Estado" not in df.columns:
        df["Estado"] = "Open"
    else:
        df["Estado"] = df["Estado"].apply(normalize_status)

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

    hoy = pd.Timestamp.today()

    pendientes = df[
        df["Estado"]
        .astype(str)
        .str.strip()
        .isin(["Open", "Pending"])
    ]

    inicio_semana = hoy - pd.Timedelta(days=hoy.weekday())
    esta_semana = df[df["Fecha"] >= inicio_semana] if "Fecha" in df.columns else df.iloc[0:0]

    pendientes = pendientes.copy()
    if "Fecha" in pendientes.columns:
        pendientes["Dias"] = (hoy - pendientes["Fecha"]).dt.days
    else:
        pendientes["Dias"] = 0

    vencidos = pendientes[pendientes["Dias"] >= 8]

    tutores = (
        pendientes["Tutor"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    tutores = tutores[tutores != ""]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("📌 Pending", len(pendientes))
    col2.metric("👨‍🏫 Tutors with load", tutores.nunique())
    col3.metric("🚨 SLA overdue", len(vencidos))
    col4.metric("📅 This week", len(esta_semana))

    st.subheader("🚨 Oldest pending cases")

    pendientes = pendientes.sort_values("Dias", ascending=False)
    columnas_home = ["ID", "Estudiante", "Curso", "Tutor", "Estado", "Tipo de solicitud", "Dias"]
    columnas_home = [col for col in columnas_home if col in pendientes.columns]

    st.dataframe(pendientes[columnas_home], width="stretch")
# ----------------------------------
# NUEVA SOLICITUD
# ----------------------------------

elif menu == "📝 New Request":

    st.header("📝 New Request")

    tipo_solicitud = st.selectbox(
        "Select request type",
        [
            "🟢 Leveling",
            "✨ Extra Class"
        ]
    )

    if tipo_solicitud == "🟢 Leveling":

        st.subheader("Leveling form")

        nuevo_id = generar_id(worksheet)

        st.text_input("ID", value=nuevo_id, disabled=True)
        fecha = st.date_input("Date")
        estudiante = st.text_input("Student name")
        edad = st.number_input("Age", min_value=5, max_value=18, step=1)
        backoffice = st.text_input("Backoffice")
        graduado = st.selectbox("Graduate", ["No", "Yes"])

        curso_inferido = inferir_curso_desde_texto(backoffice)
        if curso_inferido:
            st.info(f"Course inferred automatically: {curso_inferido}")
            curso = curso_inferido
        else:
            curso = st.selectbox("Course", sorted(cursos_disponibles))

        tutores_disponibles = obtener_tutores_disponibles(curso, spreadsheet)

        if tutores_disponibles.empty:
            st.warning(f"No active tutors are available for {curso}")
            tutor_asignado = ""
        else:
            opciones_tutor = [
                f"{row['Name']} ({row['Casos']} cases)"
                for _, row in tutores_disponibles.iterrows()
            ]
            tutor_seleccionado = st.selectbox("Assigned tutor", opciones_tutor)
            tutor_asignado = tutor_seleccionado.split(" (")[0]

        solicitud = st.selectbox(
            "Request type",
            [
                "🟢 Leveling",
                "🔵 DEMO Class",
                "🟡 Validation of age / prior knowledge",
                "🟠 Refund risk / low motivation",
                "🟣 SEN student",
                "🔴 Bad sale / expectations were not met"
            ]
        )

        observaciones = st.text_area("Observations")
        creado_por = st.text_input("Created by")

        if st.button("Save Request"):
            if not tutor_asignado:
                st.error(f"Please select an assigned tutor for {curso} before saving")
            else:
                mensaje = f"""
🚨 *New leveling request assigned*

Hello *{tutor_asignado}* 👋

A new leveling case has been assigned to you for review.

━━━━━━━━━━━━━━━━━━

👦 *Student:* {estudiante}
🎂 *Age:* {edad}
🆔 *ID:* {nuevo_id}
📚 *Course:* {curso}
📎 *Back Office:* {backoffice or 'Not provided'}
📋 *Request type:* {solicitud}

━━━━━━━━━━━━━━━━━━

📝 *Observations*

{observaciones or 'No observations provided.'}

━━━━━━━━━━━━━━━━━━

Thank you 💙
"""

                worksheet.append_row([
                    str(fecha),
                    nuevo_id,
                    estudiante,
                    edad,
                    backoffice,
                    graduado,
                    curso,
                    solicitud,
                    "Open",
                    creado_por,
                    observaciones,
                    "",
                    tutor_asignado,
                    mensaje,
                ])

                st.success(f"✅ Request {nuevo_id} created successfully")
                st.code(mensaje)

    else:

        st.subheader("Extra class form")

        nuevo_id = generar_id(worksheet_extras)

        st.text_input("ID", value=nuevo_id, disabled=True)
        fecha = st.date_input("Date")
        backoffice_estudiante = st.text_input("Student Backoffice")
        backoffice_grupo = st.text_input("Group name")
        tiempo_clase_extra = st.selectbox("Extra class duration", ["30 min", "60 min"])

        curso_inferido = inferir_curso_desde_grupo(backoffice_grupo)
        if not curso_inferido:
            texto_curso = " ".join(
                parte for parte in [backoffice_estudiante, backoffice_grupo] if parte
            )
            curso_inferido = inferir_curso_desde_texto(texto_curso)
        if curso_inferido:
            idx = sorted(cursos_disponibles).index(curso_inferido) if curso_inferido in cursos_disponibles else 0
            curso = st.selectbox("Course", sorted(cursos_disponibles), index=idx, disabled=True)
        else:
            curso = st.selectbox("Course", sorted(cursos_disponibles))

        clases_a_recuperar = st.selectbox(
            "Lessons to recover",
            ["Lesson 1", "Lesson 1 and Lesson 2", "Lesson 1 to Lesson 3", "Lesson 1 to Lesson 4"],
        )
        tipo_clase = st.selectbox(
            "Extra class type",
            ["Reinforcement", "Review", "Assessment", "New Enrollment", "Technical issues", "CS request", "Other"],
        )

        observaciones = st.text_area("Observations")
        creado_por = st.text_input("Created by")

        tutor_asignado = ""
        if backoffice_grupo:
            tutor_asignado, _ = obtener_tutor_por_grupo(backoffice_grupo, spreadsheet)
            if tutor_asignado:
                st.info(f"Tutor assigned automatically: {tutor_asignado}")
            else:
                st.warning("No tutor was found for that Group name in the Groups & Tutors sheet")

        if st.button("Save Extra Class"):
            if not tutor_asignado:
                st.error("Please enter a valid Group Backoffice so the tutor can be assigned automatically")
            else:
                mensaje = f"""
🚨 *New extra class assigned*

Hello *{tutor_asignado}* 👋

A new extra class has been assigned to you. Please request the Classroom reservation through the student BO.

━━━━━━━━━━━━━━━━━━

👦 *Student Backoffice:* {backoffice_estudiante}
👥 *Group name:* {backoffice_grupo}
📚 *Course:* {curso}
⏱️ *Duration:* {tiempo_clase_extra}
🧾 *Lessons to recover:* {clases_a_recuperar}
📋 *Extra class type:* {tipo_clase}

━━━━━━━━━━━━━━━━━━

📝 *Observations*

{observaciones or 'No observations provided.'}

Thank you 💙
"""

                worksheet_extras.append_row([
                    str(fecha),
                    nuevo_id,
                    backoffice_estudiante,
                    backoffice_grupo,
                    tiempo_clase_extra,
                    curso,
                    clases_a_recuperar,
                    tipo_clase,
                    observaciones,
                    creado_por,
                    "",
                    tutor_asignado,
                    mensaje,
                    "",
                ])

                st.success(f"✅ Extra class {nuevo_id} created successfully")
                st.code(mensaje)

# ----------------------------------
# ASIGNAR TUTOR
# ----------------------------------

elif menu == "👨‍🏫 Assign Tutor":

    st.info("The tutor assignment section is disabled in this version of the app.")

# ----------------------------------
# VER SOLICITUDES
# ----------------------------------

elif menu == "📋 View Requests":

    st.header("📋 Requests")

    frames = []
    for sheet, label in [(worksheet, "Leveling"), (worksheet_extras, "Extra Classes")]:
        df = cargar_solicitudes(sheet).copy()
        if df.empty:
            continue
        df["Fuente"] = label
        frames.append(df)

    if not frames:
        st.info("There are no registered requests")
        st.stop()

    df = pd.concat(frames, ignore_index=True)

    df.columns = df.columns.astype(str).str.strip()

    if "Estado" not in df.columns:
        df["Estado"] = "Open"

    # -----------------------------
    # FILTROS
    # -----------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        estado = st.selectbox(
            "Status",
            ["All"] + sorted(
                df["Estado"]
                .fillna("")
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )
        )

    with col2:
        curso = st.selectbox(
            "Course",
            ["All"] + sorted(
                df["Curso"]
                .fillna("")
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )
        )

    with col3:
        tutor = st.selectbox(
            "Tutor",
            ["All"] + sorted(
                df["Tutor"]
                .fillna("")
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )
        )

    with col4:
        tipo = st.selectbox(
            "Type",
            ["All", "Leveling", "Extra Classes"]
        )

    # -----------------------------
    # APLICAR FILTROS
    # -----------------------------

    filtrado = df.copy()

    if estado != "All":
        filtrado = filtrado[filtrado["Estado"].astype(str).str.strip() == estado]

    if curso != "All":
        filtrado = filtrado[filtrado["Curso"].astype(str).str.strip() == curso]

    if tutor != "All":
        filtrado = filtrado[filtrado["Tutor"].astype(str).str.strip() == tutor]

    if tipo != "All":
        filtrado = filtrado[filtrado["Fuente"] == tipo]

    # -----------------------------
    # BUSCADOR
    # -----------------------------

    buscar = st.text_input("🔍 Search student, ID, or backoffice")

    if buscar:
        buscar = buscar.lower()
        filtrado = filtrado[
            filtrado.astype(str)
            .apply(lambda fila: fila.str.lower().str.contains(buscar))
            .any(axis=1)
        ]

    # -----------------------------
    # RESULTADOS
    # -----------------------------

    st.success(f"Showing {len(filtrado)} requests")

    if "Fecha" in filtrado.columns:
        filtrado = filtrado.copy()
        filtrado["Fecha"] = pd.to_datetime(filtrado["Fecha"], errors="coerce")
        filtrado["Open days"] = (
            (pd.Timestamp.today().normalize() - filtrado["Fecha"]).dt.days.fillna(0).astype(int)
        )

        def color_sla(row):
            dias = row["Open days"]
            if pd.isna(dias):
                return [""] * len(row)
            if dias >= 8:
                return ["background-color:#ffb3b3"] * len(row)
            if dias >= 6:
                return ["background-color:#fff0b3"] * len(row)
            return [""] * len(row)

        st.dataframe(filtrado.style.apply(color_sla, axis=1), width="stretch")
    else:
        st.dataframe(filtrado, width="stretch")
# ----------------------------------
# BUSCAR CASO
# ----------------------------------

elif menu == "🔎 Search Case":

    st.header("🔎 Search Case")

    tipo_busqueda = st.selectbox(
        "Case type",
        ["Leveling", "Extra Classes", "Both"]
    )

    id_busqueda = st.text_input(
        "Enter the request ID"
    )

    if id_busqueda:

        # BUSCAR EN LEVELING Y EXTRAS

        resultados = []

        tipos_a_buscar = []
        if tipo_busqueda == "Leveling":
            tipos_a_buscar = [(worksheet, "Leveling Request")]
        elif tipo_busqueda == "Extra Classes":
            tipos_a_buscar = [(worksheet_extras, "Extra Request")]
        else:
            tipos_a_buscar = [
                (worksheet, "Leveling Request"),
                (worksheet_extras, "Extra Request")
            ]

        for sheet, etiqueta in tipos_a_buscar:
            data = leer_hoja_valores(sheet.title)

            if not data:
                continue

            df = pd.DataFrame(
                data[1:],
                columns=data[0]
            )

            df.columns = (
                df.columns
                .astype(str)
                .str.strip()
            )

            match = df[
                df["ID"]
                .astype(str)
                .str.strip()
                == str(id_busqueda).strip()
            ]

            if not match.empty:
                resultados.append((etiqueta, match.iloc[0], match))

        if not resultados:
            st.warning(
                "The ID was not found in the selected search"
            )
            st.stop()

        if len(resultados) > 1:
            opciones = [etiqueta for etiqueta, _, _ in resultados]
            etiqueta_seleccionada = st.selectbox(
                "Select the case type to view the details",
                opciones
            )
            etiqueta, fila, match = next(
                item for item in resultados if item[0] == etiqueta_seleccionada
            )
        else:
            etiqueta, fila, match = resultados[0]

        st.subheader(f"📋 Case information ({etiqueta})")

        st.write(match.T)

        # --------------------------
        # RESPUESTAS
        # --------------------------

        if etiqueta == "Extra Request":
            st.info("Case found as an extra class. No leveling result applies.")

        try:

            respuestas_data = leer_hoja_valores("answers")

            respuestas_df = pd.DataFrame(
                respuestas_data[1:],
                columns=respuestas_data[0]
            )

            respuestas_df.columns = limpiar_columnas(
                respuestas_df.columns
            )

            respuesta = respuestas_df[
                respuestas_df[
                    "ID de la solicitud que te hicieron (OJO Está en el hilo de slack donde fuiste asignado)"
                ]
                .astype(str)
                == str(id_busqueda).strip()
            ]

            if not respuesta.empty:

                st.success(
                    "✅ Result found in RESPUESTAS"
                )

                fila_respuesta = respuesta.iloc[0]

                st.subheader("📊 Leveling result")

                st.write(
                    f"**Course:** {fila_respuesta.get('Curso', 'N/A')}"
                )

                st.write(
                    f"**Group type:** {fila_respuesta.get('Tipo de grupo:', 'N/A')}"
                )

                st.write(
                    f"**Suggested level:** {fila_respuesta.get('Nivel sugerido:', 'N/A')}"
                )

                st.write(
                    f"**Nivel sugerido:** {fila_respuesta.get('Resultado nivelación:  (información para CS/ISM)', 'N/A')}"
                )

            else:

                st.info(
                    "No result found in RESPUESTAS"
                )

        except Exception as e:

            st.error(
                f"Error reading RESPUESTAS: {e}"
            )

        # --------------------------
        # RESPUESTAS GRADUADOS
        # --------------------------

        try:

            grad_data = leer_hoja_valores("answers - graduates")

            grad_df = pd.DataFrame(
                grad_data[1:],
                columns=grad_data[0]
            )

            grad_df.columns = limpiar_columnas(
                grad_df.columns
            )

            grad_df["codigo_bo"] = (
                grad_df["BO del estudiante"]
                .apply(extraer_codigo_bo)
            )

            backoffice = str(
                fila.get("Backoffice", "") or fila.get("Backoffice del Estudiante", "")
            ).strip()

            codigo_bo = extraer_codigo_bo(backoffice)

            if codigo_bo:

                resultado_grad = grad_df[
                    grad_df["codigo_bo"]
                    == codigo_bo
                ]

            else:

                resultado_grad = pd.DataFrame()

            if not resultado_grad.empty:

                st.success("🎓 Result found in answers - graduates")

                fila_grad = resultado_grad.iloc[0]

                st.subheader("🎓 Graduation result")

                st.write(
                    f"**Ready to continue?:** {fila_grad.get('¿Consideras que el(la) estudiante está apto para continuar con otro curso más avanzado dentro de kodland?', 'N/A')}"
                )

                st.write(
                    f"**Recommended course:** {fila_grad.get('Curso que recomiendas', 'N/A')}"
                )

                st.subheader("📝 Tutor feedback")

                st.info(
                    fila_grad.get(
                        'Feedback',
                        'No feedback'
                    )
                )

            else:

                st.info(
                    "No result found in answers - graduates"
                )

        except Exception as e:

            st.error(
                f"Error reading RESPUESTAS - GRADUADOS: {e}"
            )
# METRICAS
# ----------------------------------
elif menu == "📊 Metrics":

    st.header("📊 Operational Dashboard")

    def render_metrics_for_sheet(sheet, title):
        df = cargar_solicitudes(sheet)

        if df.empty:
            st.info(f"No data for {title}")
            return

        st.subheader(title)

        estados = (
            df["Estado"]
            .fillna("Open")
            .astype(str)
            .str.strip()
        )

        pendientes = df[
            estados.isin(["Open", "Pending"])
        ]

        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df))
        col2.metric("Pending", len(pendientes))
        col3.metric(
            "Assigned",
            int((pendientes["Tutor"].fillna("").astype(str).str.strip() != "").sum())
        )

        if "Fecha" in df.columns and df["Fecha"].notna().any():
            solicitudes = df[df["Fecha"].notna()].copy()
            solicitudes["Semana"] = solicitudes["Fecha"].dt.strftime("%Y-W%U")
            col_name = "Solicitud" if "Solicitud" in solicitudes.columns else "Tipo de clase extra"
            tabla_semana = pd.pivot_table(
                solicitudes,
                index="Semana",
                columns=col_name,
                aggfunc="size",
                fill_value=0
            )
            tabla_semana["Total"] = tabla_semana.sum(axis=1)
            st.dataframe(tabla_semana.reset_index(), width="stretch")

        if "Curso" in df.columns:
            cursos = [
                str(valor).strip()
                for valor in df["Curso"].fillna("")
                if str(valor).strip()
            ]
            if cursos:
                cursos_df = pd.Series(cursos).value_counts().reset_index()
                cursos_df.columns = ["Curso", "Cantidad"]
                st.dataframe(cursos_df, width="stretch")

        if "Tutor" in df.columns:
            tutores = [
                str(valor).strip()
                for valor in df["Tutor"].fillna("")
                if str(valor).strip()
            ]
            if tutores:
                tutores_df = pd.Series(tutores).value_counts().reset_index()
                tutores_df.columns = ["Tutor", "Casos"]
                st.dataframe(tutores_df, width="stretch")

        if not pendientes.empty:
            st.dataframe(
                pendientes[[
                    "ID",
                    "Curso",
                    "Tutor",
                    "Estado",
                    "Fecha"
                ]].sort_values("Fecha", ascending=False),
                width="stretch"
            )

    render_metrics_for_sheet(worksheet, "📘 Leveling")
    render_metrics_for_sheet(worksheet_extras, "✨ Extra Classes")
