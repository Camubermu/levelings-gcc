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
    "Digital Creativity 8-9",
    "Digital Creativity 10-12",
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

    data = sheet.get_all_values()

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
    data = sheet.get_all_values()

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


def calcular_carga_real(spreadsheet):

    carga = {}

    # ----------------------------------
    # RESPUESTAS (casos cerrados)
    # ----------------------------------

    respuestas_ws = spreadsheet.worksheet("respuestas")

    respuestas_data = respuestas_ws.get_all_values()

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

    grad_ws = spreadsheet.worksheet(
        "respuestas - graduados"
    )

    grad_data = grad_ws.get_all_values()

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

    tla_ws = spreadsheet.worksheet("CS")

    tla_data = tla_ws.get_all_values()

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
        "👨‍🏫 Assign Tutor",
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

    if "Estado" in df.columns:
        df["Estado"] = df["Estado"].apply(normalize_status)

    df["Fecha"] = pd.to_datetime(
        df["Fecha"],
        errors="coerce"
    )

    hoy = pd.Timestamp.today()

    pendientes = df[
        df["Estado"]
        .astype(str)
        .str.strip()
        .isin(["Open", "Pending"])
    ]

    # Casos de esta semana
    inicio_semana = hoy - pd.Timedelta(days=hoy.weekday())

    esta_semana = df[
        df["Fecha"] >= inicio_semana
    ]

    # Días abiertos
    pendientes = pendientes.copy()

    pendientes["Dias"] = (
        hoy - pendientes["Fecha"]
    ).dt.days

    # Casos vencidos
    vencidos = pendientes[
        pendientes["Dias"] >= 8
    ]

    # Tutores con casos
    tutores = (
        pendientes["Tutor"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    tutores = tutores[
        tutores != ""
    ]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "📌 Pending",
        len(pendientes)
    )

    col2.metric(
        "👨‍🏫 Tutors with load",
        tutores.nunique()
    )

    col3.metric(
        "🚨 SLA overdue",
        len(vencidos)
    )

    col4.metric(
        "📅 This week",
        len(esta_semana)
    )

    st.subheader("🚨 Oldest pending cases")

    pendientes = pendientes.sort_values(
        "Dias",
        ascending=False
    )

    st.dataframe(
        pendientes[
            [
                "ID",
                "Estudiante",
                "Curso",
                "Tutor",
                "Estado",
                "Dias"
            ]
        ],
        width="stretch"
    )
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

        st.text_input(
            "ID",
            value=nuevo_id,
            disabled=True
        )

        fecha = st.date_input("Date")

        estudiante = st.text_input(
            "Student name"
        )

        edad = st.number_input(
            "Age",
            min_value=5,
            max_value=18,
            step=1
        )

        backoffice = st.text_input(
            "Backoffice"
        )

        graduado = st.selectbox(
            "Graduate",
            ["No", "Yes"]
        )

        curso = st.selectbox(
            "Course",
            sorted(cursos_disponibles)
        )

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

        observaciones = st.text_area(
            "Observations"
        )

        creado_por = st.text_input(
            "Created by"
        )

        if st.button("Save Request"):

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
                "",
                ""
            ])

            st.success(
                f"✅ Request {nuevo_id} created successfully"
            )

    else:

        st.subheader("Extra class form")

        nuevo_id = generar_id(worksheet_extras)

        st.text_input(
            "ID",
            value=nuevo_id,
            disabled=True
        )

        fecha = st.date_input("Date")

        backoffice_estudiante = st.text_input(
            "Student Backoffice"
        )

        backoffice_grupo = st.text_input(
            "Group Backoffice"
        )

        tiempo_clase_extra = st.selectbox(
            "Extra class duration",
            ["30 min", "60 min"]
        )

        curso = st.selectbox(
            "Course",
            sorted(cursos_disponibles)
        )

        clases_a_recuperar = st.selectbox(
            "Lessons to recover",
            ["Lesson1", "Lesson 1 to Lesson 2", "Lesson 1 to Lesson 3", "Lesson 1 Lesson 4"]
        )

        tipo_clase = st.selectbox(
            "Extra class type",
            ["Reinforcement", "Review", "Assessment", "New Enrollment", "Other"]
        )

        observaciones = st.text_area(
            "Observations"
        )

        creado_por = st.text_input(
            "Created by"
        )

        if st.button("Save Extra Class"):

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
                "",
                "",
                ""
            ])

            st.success(
                f"✅ Extra class {nuevo_id} created successfully"
            )

# ----------------------------------
# ASIGNAR TUTOR
# ----------------------------------

elif menu == "👨‍🏫 Assign Tutor":

    st.header("👨‍🏫 Assign Tutor")

    tipo_asignacion = st.selectbox(
        "Select assignment type",
        [
            "Leveling",
            "Extra Class"
        ]
    )

    target_sheet = (
        worksheet if tipo_asignacion == "Leveling"
        else worksheet_extras
    )

    data = target_sheet.get_all_values()

    df = pd.DataFrame(
        data[1:],
        columns=data[0]
    )

    if "Estado" not in df.columns:
        df["Estado"] = "Open"

    df["Estado"] = df["Estado"].apply(normalize_status)

    pendientes = df[
        df["Estado"]
        .fillna("Open")
        .astype(str)
        .str.strip()
        .isin(["Open", "Pending", ""])
    ]

    if pendientes.empty:

        st.success(
            "There are no open requests"
        )

    else:

        solicitud_id = st.selectbox(
            "Select a request",
            pendientes["ID"]
        )

        fila = pendientes[
            pendientes["ID"] == solicitud_id
        ].iloc[0]

        st.subheader("Information")

        if tipo_asignacion == "Leveling":
            st.write(
                f"**Student:** {fila.get('Estudiante', '')}"
            )

            st.write(
                f"**Age:** {fila.get('Edad', '')}"
            )

            st.write(
                f"**Course:** {fila.get('Curso', '')}"
            )

            st.write(
                f"**Request:** {fila.get('Solicitud', '')}"
            )

            st.write(
                f"**Observations:** {fila.get('Observaciones', '')}"
            )
        else:
            st.write(
                f"**Student Backoffice:** {fila.get('Backoffice del Estudiante', '')}"
            )

            st.write(
                f"**Group Backoffice:** {fila.get('Backoffice del grupo', '')}"
            )

            st.write(
                f"**Extra class duration:** {fila.get('Tiempo de la clase extra', '')}"
            )

            st.write(
                f"**Course:** {fila.get('Curso', '')}"
            )

            st.write(
                f"**Extra class type:** {fila.get('Tipo de clase extra', '')}"
            )

            st.write(
                f"**Lessons to recover:** {fila.get('Clases a recuperar', '')}"
            )

            st.write(
                f"**Observations:** {fila.get('Observaciones', '')}"
            )
        
        # ----------------------------------
        # CARGA DE TUTORES
        # ----------------------------------

        tts_ws = spreadsheet.worksheet("TTS")

        tts_data = tts_ws.get_all_records()

        tts_df = pd.DataFrame(tts_data)

        curso_solicitado = fila["Curso"]

        # Limpiar nombres de columnas
        tts_df.columns = (
            tts_df.columns
            .astype(str)
            .str.strip()
        )

        # Verificar que exista el curso
        if curso_solicitado not in tts_df.columns:

            st.error(
                f"The course '{curso_solicitado}' does not exist in the TTS sheet"
            )

            st.stop()
        # Solo tutores activos para ese curso

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
                tts_df[curso_solicitado]
                .astype(str)
                .str.strip()
                .str.upper()
                == "TRUE"
            )
        ]
        carga_real = {}
        try:

            carga_real = calcular_carga_real(
                spreadsheet
            )

        except Exception as e:

            st.warning(
                f"Could not calculate tutor load: {e}"
            )

        tutores_curso["Casos"] = (
            tutores_curso["Name"]
            .map(carga_real)
            .fillna(0)
            .astype(int)
        )

        tutores_curso = (
            tutores_curso
            .sort_values("Casos")
        )

            

        if tutores_curso.empty:

            st.warning(
                f"There are no active tutors for {curso_solicitado}"
            )

            st.stop()

        # Lista de tutores

        opciones_tutor = [
            f"{row['Name']} ({row['Casos']} cases)"
            for _, row in tutores_curso.iterrows()
        ]

        tutor_seleccionado = st.selectbox(
            "Tutor",
            opciones_tutor
        )

        tutor = tutor_seleccionado.split(" (")[0]

        # Elegir TL 

        tl_options = sorted(
            tts_df["Team Leader"]
            .dropna()
            .astype(str)
            .unique()
        )

        tl = st.selectbox(
            "TL",
            tl_options
        )

        if st.button("Assign Tutor"):

            if tipo_asignacion == "Leveling":
                mensaje = f"""
🚨 *New request assigned*

Hello *{tutor}* 👋

A new case has been assigned to you for review.

━━━━━━━━━━━━━━━━━━

👦 *Student:* {fila['Estudiante']}
🎂 *Age:* {fila['Edad']}
🆔 *ID:* {fila['ID']}
📚 *Course:* {fila['Curso']}
📋 *Request type:* {fila['Solicitud']}

━━━━━━━━━━━━━━━━━━

📝 *Observations*

{fila['Observaciones']}

━━━━━━━━━━━━━━━━━━

⏰ *Important*

This case must be worked before it reaches *8 open days* to maintain SLA compliance.

Once you finish the session, please record the result here:

https://docs.google.com/forms/d/e/1FAIpQLSegzGGAwN9u5SLUsXszXX6eSzgsmZL2kctmJUyenpgn07g36g/viewform

Thank you 💙
"""
            else:
                mensaje = f"""
🚨 *New extra class assigned*

Hello *{tutor}* 👋

A new extra class has been assigned to you. Please request the Classroom room reservation through the student BO.

━━━━━━━━━━━━━━━━━━

👦 *Student Backoffice:* {fila.get('Backoffice del Estudiante', '')}
📚 *Course:* {fila.get('Curso', '')}
⏱️ *Duration:* {fila.get('Tiempo de la clase extra', '')}
🧾 *Lessons to recover:* {fila.get('Clases a recuperar', '')}
📋 *Extra class type:* {fila.get('Tipo de clase extra', '')}

━━━━━━━━━━━━━━━━━━

📝 *Observations*

{fila.get('Observaciones', '')}

Thank you 💙
"""

            headers = target_sheet.row_values(1)

            def get_col_idx(name):
                return headers.index(name) + 1

            ids = target_sheet.col_values(2)

            for i, valor in enumerate(ids):

                if valor == fila["ID"]:

                    fila_sheet = i + 1

                    if "TL" in headers:
                        target_sheet.update_cell(fila_sheet, get_col_idx("TL"), tl)

                    if "Tutor" in headers:
                        target_sheet.update_cell(fila_sheet, get_col_idx("Tutor"), tutor)

                    if "Mensaje" in headers:
                        target_sheet.update_cell(fila_sheet, get_col_idx("Mensaje"), mensaje)

                    if "Estado" in headers:
                        target_sheet.update_cell(fila_sheet, get_col_idx("Estado"), "Pending")
                    elif "Enviado a Slack" in headers:
                        target_sheet.update_cell(fila_sheet, get_col_idx("Enviado a Slack"), "Sí")

                    break

            st.success(
                "✅ Tutor assigned successfully"
            )

            st.code(
                mensaje
            )

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
            data = sheet.get_all_values()

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

            respuestas_ws = spreadsheet.worksheet(
                "answers"
            )

            respuestas_data = respuestas_ws.get_all_values()

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

            grad_ws = spreadsheet.worksheet(
                "answers - graduates"
            )

            grad_data = grad_ws.get_all_values()

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
