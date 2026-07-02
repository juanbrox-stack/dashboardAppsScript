"""
Módulo de control de proyectos Apps Script para el dashboard Streamlit.

Requiere en .streamlit/secrets.toml algo así:

[gsheets]
sheet_id_control = "PON_AQUI_EL_ID_DE_TU_SHEET_DE_CONTROL"

[apps_script.novedades]
url = "https://script.google.com/macros/s/XXXXX/exec"
token = "uuid-generado-con-setupToken"
funciones = ["procesarNovedades"]

[apps_script.actuaciones_catalogo]
url = "https://script.google.com/macros/s/YYYYY/exec"
token = "otro-uuid"
funciones = ["sincronizarCatalogo", "limpiarBlacklist"]

Añade una sección [apps_script.<clave>] por cada proyecto que quieras
controlar desde el dashboard. La clave es libre, solo se usa como id interno.
"""

import time
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


@st.cache_resource
def _cliente_gspread():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def cargar_estado_proyectos() -> pd.DataFrame:
    """
    Lee la hoja 'Log' de la Sheet de control y devuelve, por proyecto,
    la última ejecución registrada (estado, mensaje, fecha).
    """
    gc = _cliente_gspread()
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id_control"])
    hoja = sh.worksheet("Log")
    registros = hoja.get_all_records()

    if not registros:
        return pd.DataFrame(
            columns=["Proyecto", "Función", "Estado", "Mensaje", "Inicio", "Duración (s)"]
        )

    df = pd.DataFrame(registros)
    df["Inicio"] = pd.to_datetime(df["Inicio"], errors="coerce")

    # Nos quedamos con la última ejecución de cada combinación proyecto+función
    ultima = (
        df.sort_values("Inicio")
        .groupby(["Proyecto", "Función"], as_index=False)
        .tail(1)
        .sort_values("Inicio", ascending=False)
    )
    return ultima


def ejecutar_proyecto(clave_proyecto: str, nombre_funcion: str) -> dict:
    """
    Lanza una función remota en un proyecto Apps Script vía su Web App.
    clave_proyecto debe coincidir con una sección de st.secrets["apps_script"].
    """
    config = st.secrets["apps_script"][clave_proyecto]
    payload = {"token": config["token"], "funcion": nombre_funcion}

    try:
        resp = requests.post(config["url"], json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}


def _badge_estado(estado: str) -> str:
    if estado == "OK":
        return "🟢 OK"
    if estado == "ERROR":
        return "🔴 ERROR"
    return "⚪ Sin datos"


def render_panel_control():
    """
    Pinta el panel de control: un bloque por proyecto configurado en
    st.secrets["apps_script"], con su último estado y botones para
    lanzar cada función disponible bajo demanda.
    """
    st.subheader("Control de proyectos Apps Script")

    col_refrescar, _ = st.columns([1, 5])
    with col_refrescar:
        if st.button("🔄 Refrescar estado"):
            st.cache_data.clear()

    estado_df = cargar_estado_proyectos()
    proyectos_config = st.secrets.get("apps_script", {})

    if not proyectos_config:
        st.info("No hay proyectos configurados todavía en st.secrets['apps_script'].")
        return

    for clave, config in proyectos_config.items():
        with st.container(border=True):
            st.markdown(f"**{clave}**")

            filas_proyecto = estado_df[estado_df["Proyecto"] == clave] if not estado_df.empty else estado_df

            for funcion in config.get("funciones", []):
                fila = filas_proyecto[filas_proyecto["Función"] == funcion] if not filas_proyecto.empty else filas_proyecto
                c1, c2, c3 = st.columns([2, 3, 1])

                with c1:
                    st.write(f"`{funcion}`")

                with c2:
                    if fila is not None and not fila.empty:
                        r = fila.iloc[0]
                        st.write(f"{_badge_estado(r['Estado'])} · {r['Inicio']}")
                        if r["Estado"] == "ERROR" and r["Mensaje"]:
                            with st.expander("Ver error"):
                                st.code(r["Mensaje"])
                    else:
                        st.write(_badge_estado(""))

                with c3:
                    if st.button("Ejecutar", key=f"run_{clave}_{funcion}"):
                        with st.spinner(f"Ejecutando {funcion}..."):
                            resultado = ejecutar_proyecto(clave, funcion)
                        if resultado.get("ok"):
                            st.success("Lanzado correctamente")
                        else:
                            st.error(resultado.get("error", "Error desconocido"))
                        time.sleep(1)
                        st.rerun()


# ---------------------------------------------------------------------------
# Punto de entrada: esto es lo que hace que la app pinte algo al desplegarla
# como aplicación independiente en Streamlit Cloud. Si en el futuro importas
# este archivo como módulo desde otro dashboard (en vez de desplegarlo solo),
# puedes quitar este bloque y llamar a render_panel_control() tú mismo desde
# el archivo principal.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Control Apps Script",
    page_icon="🛠️",
    layout="wide",
)
st.title("🛠️ Control de Apps Script")
render_panel_control()
