import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------------
# CONFIG
# ----------------------------------

st.set_page_config(
    page_title="Leveling Dashboard",
    layout="wide"
)

st.title("🚀 Leveling Dashboard")

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
    "https://docs.google.com/spreadsheets/d/1sTfSu3-l-uwcuG5ZHFWr9f52LeyMVxf725PvNEr89cU/edit"
)

worksheet = spreadsheet.worksheet(
    "LEVELING_REQUESTS"
)

# ----------------------------------
# GENERAR ID
# ----------------------------------

def generar_id():

    data = worksheet.get_all_values()

    ids = []

    for fila in data[1:]:

        try:
            ids.append(int(str(fila[1]).strip()))
        except:
            pass

    # Si aún no hay solicitudes,
    # empezar desde la 3600
    if not ids:
        return "3600"

    ultimo = max(ids)

    # Si por alguna razón el máximo es menor a 3600,
    # continuar desde 3600
    if ultimo < 3600:
        return "3600"

    return str(ultimo + 1)

# ----------------------------------
# EXTRAERC CODIGO 
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

    tla_ws = spreadsheet.worksheet("TLa")

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
    "Navegación",
    [
        "🏠 Inicio",
        "📝 Nueva Solicitud",
        "👨‍🏫 Asignar Tutor",
        "📋 Ver Solicitudes",
        "🔎 Buscar Caso",
        "📊 Métricas"
    ]
)
# ----------------------------------
# INICIO
# ----------------------------------

if menu == "🏠 Inicio":

    st.header("🏠 Resumen Operativo")

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

    df["Fecha"] = pd.to_datetime(
        df["Fecha"],
        errors="coerce"
    )

    hoy = pd.Timestamp.today()

    # Casos pendientes
    pendientes = df[
        df["Estado"]
        .astype(str)
        .str.strip()
        == "Pendiente"
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
        "📌 Pendientes",
        len(pendientes)
    )

    col2.metric(
        "👨‍🏫 Tutores con carga",
        tutores.nunique()
    )

    col3.metric(
        "🚨 SLA vencido",
        len(vencidos)
    )

    col4.metric(
        "📅 Esta semana",
        len(esta_semana)
    )

    st.subheader("🚨 Casos pendientes más antiguos")

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
        use_container_width=True
    )
# ----------------------------------
# NUEVA SOLICITUD
# ----------------------------------

elif menu == "📝 Nueva Solicitud":

    st.header("📝 Nueva Solicitud")

    nuevo_id = generar_id()

    st.text_input(
        "ID",
        value=nuevo_id,
        disabled=True
    )

    fecha = st.date_input("Fecha")

    estudiante = st.text_input(
        "Nombre del estudiante"
    )

    edad = st.number_input(
        "Edad",
        min_value=5,
        max_value=18,
        step=1
    )

    backoffice = st.text_input(
        "Backoffice"
    )

    graduado = st.selectbox(
        "Graduado",
        ["No", "Sí"]
    )

    cursos_disponibles = [
        "Python 10-12",
        "Python Pro",
        "Scratch 8-9",
        "Scratch 10-12",
        "Web",
        "FWD",
        "FWD Pro",
        "Roblox 8-9",
        "Roblox 10-12",
        "UNITY",
        "Digital Creativity 8-9",
        "Digital Creativity 10-12",
        "Graphic Design",
        "Illustration",
        "Minecraft",
        "Minecraft Level 2",
        "Drawing on Paper",
        "Math 8-10",
        "Math 10-12",
        "Early Math 5-8",
        "FunTech"
    ]

    curso = st.selectbox(
        "Curso",
        sorted(cursos_disponibles)
    )

    solicitud = st.selectbox(
        "Tipo de solicitud",
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
        "Observaciones"
    )

    creado_por = st.text_input(
        "Creado por"
    )

    if st.button("Guardar Solicitud"):

        worksheet.append_row([
            str(fecha),
            nuevo_id,
            estudiante,
            edad,
            backoffice,
            graduado,
            curso,
            solicitud,
            "Abierto",
            creado_por,
            observaciones,
            "",
            "",
            ""
        ])

        st.success(
            f"✅ Solicitud {nuevo_id} creada correctamente"
        )

# ----------------------------------
# ASIGNAR TUTOR
# ----------------------------------

elif menu == "👨‍🏫 Asignar Tutor":

    st.header("👨‍🏫 Asignar Tutor")

    data = worksheet.get_all_values()

    df = pd.DataFrame(
        data[1:],
        columns=data[0]
    )

    pendientes = df[
        df["Estado"]
        .astype(str)
        .str.lower()
        == "abierto"
    ]

    if pendientes.empty:

        st.success(
            "No hay solicitudes abiertas"
        )

    else:

        solicitud_id = st.selectbox(
            "Selecciona una solicitud",
            pendientes["ID"]
        )

        fila = pendientes[
            pendientes["ID"] == solicitud_id
        ].iloc[0]

        st.subheader("Información")

        st.write(
            f"**Estudiante:** {fila['Estudiante']}"
        )

        st.write(
            f"**Edad:** {fila['Edad']}"
        )

        st.write(
            f"**Curso:** {fila['Curso']}"
        )

        st.write(
            f"**Solicitud:** {fila['Solicitud']}"
        )

        st.write(
            f"**Observaciones:** {fila['Observaciones']}"
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
                f"El curso '{curso_solicitado}' no existe en la hoja TTS"
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
        try:

            carga_real = calcular_carga_real(
                spreadsheet
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

        except Exception as e:

            st.warning(
                f"No fue posible calcular cargas: {e}"
            )

            

        if tutores_curso.empty:

            st.warning(
                f"No hay tutores activos para {curso_solicitado}"
            )

            st.stop()

        # Lista de tutores

        opciones_tutor = [
            f"{row['Name']} ({row['Casos']} casos)"
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

        if st.button("Asignar Tutor"):

            mensaje = f"""
🚨 *Nueva solicitud asignada*

Hola *{tutor}* 👋

Se te ha asignado un nuevo caso para revisión.

━━━━━━━━━━━━━━━━━━

👦 *Estudiante:* {fila['Estudiante']}
🎂 *Edad:* {fila['Edad']}
🆔 *ID:* {fila['ID']}
📚 *Curso:* {fila['Curso']}
📋 *Tipo de solicitud:* {fila['Solicitud']}

━━━━━━━━━━━━━━━━━━

📝 *Observaciones*

{fila['Observaciones']}

━━━━━━━━━━━━━━━━━━

⏰ *Importante*

Este caso debe ser trabajado antes de cumplir *8 días abiertos* para mantener el SLA del proceso.

Una vez finalices la sesión, registra el resultado aquí:

https://docs.google.com/forms/d/e/1FAIpQLSegzGGAwN9u5SLUsXszXX6eSzgsmZL2kctmJUyenpgn07g36g/viewform

Gracias 💙
"""

            ids = worksheet.col_values(2)

            for i, valor in enumerate(ids):

                if valor == fila["ID"]:

                    fila_sheet = i + 1

                    worksheet.update_cell(
                        fila_sheet,
                        12,
                        tl
                    )

                    worksheet.update_cell(
                        fila_sheet,
                        13,
                        tutor
                    )

                    worksheet.update_cell(
                        fila_sheet,
                        14,
                        mensaje
                    )

                    worksheet.update_cell(
                        fila_sheet,
                        9,
                        "Pendiente"
                    )

                    break

            st.success(
                "✅ Tutor asignado correctamente"
            )

            st.code(
                mensaje
            )

# ----------------------------------
# VER SOLICITUDES
# ----------------------------------

elif menu == "📋 Ver Solicitudes":

    st.header("📋 Solicitudes")

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

    # -----------------------------
    # FILTROS
    # -----------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        estado = st.selectbox(
            "Estado",
            ["Todos"] + sorted(
                df["Estado"]
                .fillna("")
                .unique()
                .tolist()
            )
        )

    with col2:

        curso = st.selectbox(
            "Curso",
            ["Todos"] + sorted(
                df["Curso"]
                .fillna("")
                .unique()
                .tolist()
            )
        )

    with col3:

        tutor = st.selectbox(
            "Tutor",
            ["Todos"] + sorted(
                df["Tutor"]
                .fillna("")
                .unique()
                .tolist()
            )
        )

    with col4:

        solicitud = st.selectbox(
            "Tipo",
            ["Todos"] + sorted(
                df["Solicitud"]
                .fillna("")
                .unique()
                .tolist()
            )
        )

    # -----------------------------
    # APLICAR FILTROS
    # -----------------------------

    filtrado = df.copy()

    if estado != "Todos":
        filtrado = filtrado[
            filtrado["Estado"] == estado
        ]

    if curso != "Todos":
        filtrado = filtrado[
            filtrado["Curso"] == curso
        ]

    if tutor != "Todos":
        filtrado = filtrado[
            filtrado["Tutor"] == tutor
        ]

    if solicitud != "Todos":
        filtrado = filtrado[
            filtrado["Solicitud"] == solicitud
        ]

    # -----------------------------
    # BUSCADOR
    # -----------------------------

    buscar = st.text_input(
        "🔍 Buscar estudiante o ID"
    )

    if buscar:

        buscar = buscar.lower()

        filtrado = filtrado[
            filtrado.astype(str)
            .apply(
                lambda fila:
                fila.str.lower().str.contains(buscar)
            )
            .any(axis=1)
        ]

    # -----------------------------
    # RESULTADOS
    # -----------------------------

    st.success(
        f"Mostrando {len(filtrado)} solicitudes"
    )

    df["Fecha"] = pd.to_datetime(
        df["Fecha"],
        errors="coerce"
    )

    df["Días abiertos"] = (
        (
            pd.Timestamp.today().normalize()
            - df["Fecha"]
        ).dt.days
        .fillna(0)
        .astype(int)
    )
    
    def color_sla(row):

        dias = row["Días abiertos"]

        if pd.isna(dias):
            return [""] * len(row)

        if dias >= 8:
            return ["background-color:#ffb3b3"] * len(row)

        elif dias >= 6:
            return ["background-color:#fff0b3"] * len(row)

        return [""] * len(row)

    st.dataframe(
        df.style.apply(color_sla, axis=1),
        use_container_width=True
    )
# ----------------------------------
# BUSCAR CASO
# ----------------------------------

elif menu == "🔎 Buscar Caso":

    st.header("🔎 Buscar Caso")

    id_busqueda = st.text_input(
        "Ingrese el ID de la solicitud"
    )

    if id_busqueda:

        # LEVELING REQUESTS

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

        # Buscar en LEVELING REQUESTS

        solicitud = df[
            df["ID"]
            .astype(str)
            .str.strip()
            == str(id_busqueda).strip()
        ]

        if not solicitud.empty:

            fila = solicitud.iloc[0]

            st.subheader("📋 Información del caso (Leveling Request)")

            st.write(solicitud.T)

        else:

            st.info(
                "No se encontró en LEVELING_REQUESTS. Buscando en TLa..."
            )

    
        # --------------------------
        # TLA
        # --------------------------

        try:

            tla_ws = spreadsheet.worksheet(
                "TLa"
            )

            tla_data = tla_ws.get_all_values()

            tla_df = pd.DataFrame(
                tla_data[1:],
                columns=tla_data[0]
            )

            tla_df.columns = limpiar_columnas(
                tla_df.columns
            )

            tla_match = tla_df[
                tla_df["ID"]
                .astype(str)
                == str(id_busqueda).strip()
            ]

            if tla_match.empty:

                st.warning(
                    "No se encontró el ID en TLa"
                )

            else:

                st.success(
                    "✅ ID encontrado en TLa"
                )

                fila_tla = tla_match.iloc[0]

                st.subheader("📋 Información del Caso (TLa)")

                st.write(f"**ID:** {fila_tla['ID']}")
                st.write(f"**Edad:** {fila_tla['Age']}")
                st.write(f"**Curso actual:** {fila_tla['Curso ACTUAL']}")
                st.write(f"**Curso sugerido:** {fila_tla['Course para ofrecer \n(puede ser el mismo)']}")
                st.write(f"**Descripción:** {fila_tla['Descripción']}")

                bo_url = tla_match[
                    "Link al Back Office del estudiante"
                ].iloc[0]

                codigo_bo = extraer_codigo_bo(
                    bo_url
                )

        except Exception as e:

            st.error(
                f"Error leyendo TLa: {e}"
            )

            st.stop()
        
        if not tla_match.empty:

        # --------------------------
        # RESPUESTAS
        # --------------------------

            try:

                respuestas_ws = spreadsheet.worksheet(
                    "respuestas"
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
                    == str(id_busqueda)
                ]

                if not respuesta.empty:

                    st.success(
                        "✅ Resultado encontrado en RESPUESTAS"
                    )

                    fila_respuesta = respuesta.iloc[0]

                    st.subheader("📊 Resultado de la Nivelación")

                    st.write(
                        f"**Curso:** {fila_respuesta.get('Curso', 'N/A')}"
                    )

                    st.write(
                        f"**Tipo de grupo:** {fila_respuesta.get('Tipo de grupo:', 'N/A')}"
                    )

                    st.write(
                        f"**Nivel sugerido:** {fila_respuesta.get('Nivel sugerido:', 'N/A')}"
                    )

                    st.write(
                        f"**Nivel sugerido:** {fila_respuesta.get('Resultado nivelación:  (información para CS/ISM)', 'N/A')}"
                    )


            except Exception as e:

                st.error(
                    f"No se encontró respuesta en RESPUESTAS"
                )

            # --------------------------
            # RESPUESTAS GRADUADOS
            # --------------------------

            try:

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

                grad_df["codigo_bo"] = (
                    grad_df["BO del estudiante"]
                    .apply(extraer_codigo_bo)
                )

                resultado_grad = grad_df[
                    grad_df["codigo_bo"]
                    == codigo_bo
                ]

                if not resultado_grad.empty:

                    st.success("🎓 Resultado encontrado en RESPUESTAS - GRADUADOS")

                    fila_grad = resultado_grad.iloc[0]

                    ...   

                else:

                    st.success(
                    "🎓 Resultado encontrado en RESPUESTAS - GRADUADOS"
                )

                fila_grad = resultado_grad.iloc[0]

                st.subheader("🎓 Resultado de Graduación")

                st.write(
                    f"**¿Apto para continuar?:** {fila_grad.get('¿Consideras que el(la) estudiante está apto para continuar con otro curso más avanzado dentro de kodland?', 'N/A')}"
                )

                st.write(
                    f"**Curso recomendado:** {fila_grad.get('Curso que recomiendas', 'N/A')}"
                )

                st.subheader("📝 Feedback del Tutor")

                st.info(
                    fila_grad.get(
                        'Feedback',
                        'Sin feedback'
                    )
                )

            except Exception as e:

                st.error(
                    f"No se encontró respuesta en RESPUESTAS - GRADUADOS"
                )

# ----------------------------------
# METRICAS
# ----------------------------------
elif menu == "📊 Métricas":

    import re

    st.header("📊 Dashboard Operativo")

    # ==================================
    # CARGAR LEVELING
    # ==================================

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

    df = df.replace(
        r'^\s*$',
        pd.NA,
        regex=True
    ).dropna(how="all")

    # ==================================
    # FECHA
    # ==================================

    df["Fecha"] = pd.to_datetime(
        df["Fecha"],
        errors="coerce"
    )

    # ==================================
    # PENDIENTES
    # ==================================

    estado = (
        df["Estado"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    pendientes = df[
        estado.eq("Pendiente")
    ]

    # ==================================
    # SOLICITUDES POR SEMANA
    # ==================================

    st.subheader("📅 Solicitudes por semana")

    solicitudes = df.copy()

    solicitudes = solicitudes[
        solicitudes["Fecha"].notna()
    ]

    solicitudes["Semana"] = (
        solicitudes["Fecha"]
        .dt.strftime("%Y-W%U")
    )

    solicitudes["Solicitud"] = (
        solicitudes["Solicitud"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    solicitudes = solicitudes[
        solicitudes["Solicitud"] != ""
    ]

    tabla_semana = pd.pivot_table(
        solicitudes,
        index="Semana",
        columns="Solicitud",
        aggfunc="size",
        fill_value=0
    )

    tabla_semana["Total"] = (
        tabla_semana.sum(axis=1)
    )

    tabla_semana = (
        tabla_semana
        .sort_index(
            ascending=False
        )
    )

    st.dataframe(
        tabla_semana.reset_index(),
        use_container_width=True
    )

    # ==================================
    # CURSOS SOLICITADOS
    # ==================================

    st.subheader("📚 Cursos solicitados")

    cursos = []

    for valor in df["Curso"].fillna(""):

        valor = str(valor).strip()

        if valor:
            cursos.append(valor)

    if cursos:

        cursos_df = (
            pd.Series(cursos)
            .value_counts()
            .reset_index()
        )

        cursos_df.columns = [
            "Curso",
            "Cantidad"
        ]

        st.dataframe(
            cursos_df,
            use_container_width=True
        )

    # ==================================
    # CASOS POR TUTOR
    # ==================================

    st.subheader("👨‍🏫 Casos por tutor")

    tutores = []

    for valor in df["Tutor"].fillna(""):

        valor = str(valor).strip()

        if valor:
            tutores.append(valor)

    if tutores:

        tutores_df = (
            pd.Series(tutores)
            .value_counts()
            .reset_index()
        )

        tutores_df.columns = [
            "Tutor",
            "Casos"
        ]

        st.dataframe(
            tutores_df,
            use_container_width=True
        )

    # ==================================
    # PENDIENTES POR TUTOR
    # ==================================

    st.subheader("🚨 Carga actual de tutores")

    pendientes = (
        df[
            df["Estado"]
            .fillna("")
            .str.strip()
            .eq("Pendiente")
        ]
    )

    carga = (
        pendientes.groupby("Tutor")
        .size()
        .reset_index(name="Pendientes")
    )

    carga = carga[
        carga["Tutor"].str.strip() != ""
    ]

    carga = carga.sort_values(
        "Pendientes",
        ascending=False
    )

    def estado(cantidad):
        if cantidad >= 6:
            return "🔴 Alta"

        elif cantidad >= 4:
            return "🟡 Media"

        return "🟢 Baja"

    carga["Carga"] = carga["Pendientes"].apply(estado)
    
    st.dataframe(
        carga,
        use_container_width=True,
        hide_index=True
    )

    # ==================================
    # PENDIENTES POR SEMANA
    # ==================================

    pend = pendientes.copy()

    pend["Semana"] = (
        pend["Fecha"]
        .dt.strftime("%Y-W%U")
    )

    tabla_pend = (
        pend.groupby("Semana")
        .size()
        .reset_index(name="Pendientes")
        .sort_values(
            "Semana",
            ascending=False
        )
    )

    st.subheader(
        "📅 Pendientes por semana"
    )

    st.dataframe(
        tabla_pend,
        use_container_width=True
    )

    # ==================================
    # LISTADO PENDIENTES
    # ==================================

    st.subheader(
        f"🚨 Casos pendientes ({len(pendientes)})"
    )

    st.dataframe(
        pendientes,
        use_container_width=True
    )
