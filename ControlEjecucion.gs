/**
 * =========================================================================
 * PLANTILLA: Control de Ejecución para proyectos Apps Script
 * =========================================================================
 * Pega este archivo en cada proyecto de Apps Script que quieras monitorizar
 * desde el dashboard de Streamlit. Solo tienes que:
 *   1. Ajustar SHEET_ID_CONTROL con el ID de tu Sheet central de control.
 *   2. Definir un token secreto en Propiedades del script (ver setup abajo).
 *   3. Envolver tus funciones de trigger con ejecutarConControl_().
 *   4. Registrar las funciones "lanzables" en el mapa FUNCIONES_DISPONIBLES.
 * =========================================================================
 */

// ID de la Google Sheet central donde se registran todas las ejecuciones
// de todos tus proyectos (una sola sheet para todo el dashboard).
const SHEET_ID_CONTROL = 'https://docs.google.com/spreadsheets/d/1VbAWNObgiG42PUicXn4udzIA0Qw_wU6kKIMExKfk86I/edit?gid=0#gid=0';
const NOMBRE_HOJA_LOG = 'Log';

// Nombre identificativo de ESTE proyecto (aparecerá en el dashboard).
// Cámbialo en cada proyecto donde pegues esta plantilla.
const NOMBRE_PROYECTO = 'NombreDeEsteProyecto';

/**
 * SETUP INICIAL (ejecutar una vez manualmente desde el editor):
 * Genera un token aleatorio y lo guarda en las Propiedades del script,
 * para que doPost() pueda validar las peticiones del dashboard.
 */
function setupToken() {
  const token = Utilities.getUuid();
  PropertiesService.getScriptProperties().setProperty('DASHBOARD_TOKEN', token);
  Logger.log('Token generado (cópialo a st.secrets en Streamlit): ' + token);
}

/**
 * Envuelve cualquier función de trigger con captura de errores y logging
 * automático a la Sheet de control. Úsalo así en tu trigger:
 *
 *   function miTriggerDiario() {
 *     ejecutarConControl_('procesarPedidos', procesarPedidos);
 *   }
 *
 * @param {string} nombreFuncion Nombre legible de la tarea (para el log)
 * @param {Function} fn Función a ejecutar (sin argumentos)
 * @return {*} El resultado de fn(), o null si falló
 */
function ejecutarConControl_(nombreFuncion, fn) {
  const inicio = new Date();
  try {
    const resultado = fn();
    registrarEjecucion_(nombreFuncion, 'OK', '', inicio);
    return resultado;
  } catch (err) {
    registrarEjecucion_(nombreFuncion, 'ERROR', err.message + '\n' + err.stack, inicio);
    // Relanzamos el error para que siga apareciendo en el panel nativo
    // de "Ejecuciones" de Apps Script si quieres consultarlo ahí también.
    throw err;
  }
}

/**
 * Escribe una fila en la Sheet de control con el resultado de la ejecución.
 * Estructura de columnas esperada en la hoja "Log":
 * Proyecto | Función | Estado | Mensaje | Inicio | Duración (s)
 */
function registrarEjecucion_(nombreFuncion, estado, mensaje, inicio) {
  const ss = SpreadsheetApp.openById(SHEET_ID_CONTROL);
  let hoja = ss.getSheetByName(NOMBRE_HOJA_LOG);
  if (!hoja) {
    hoja = ss.insertSheet(NOMBRE_HOJA_LOG);
    hoja.appendRow(['Proyecto', 'Función', 'Estado', 'Mensaje', 'Inicio', 'Duración (s)']);
  }
  const duracion = (new Date() - inicio) / 1000;
  hoja.appendRow([
    NOMBRE_PROYECTO,
    nombreFuncion,
    estado,
    mensaje,
    inicio,
    duracion
  ]);
}

/**
 * Mapa de funciones que el dashboard puede lanzar remotamente.
 * Añade aquí cada función "lanzable a demanda" de este proyecto.
 */
const FUNCIONES_DISPONIBLES = {
  // 'procesarPedidos': procesarPedidos,
  // 'sincronizarStock': sincronizarStock,
};

/**
 * Endpoint que recibe las peticiones del dashboard de Streamlit.
 * Espera un POST con JSON: { "token": "...", "funcion": "nombreFuncion" }
 *
 * Despliega esto como Web App:
 *   Implementar > Nueva implementación > Aplicación web
 *   Ejecutar como: Yo
 *   Quién tiene acceso: Cualquiera
 * Copia la URL resultante a st.secrets en Streamlit.
 */
function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return respuestaJson_({ ok: false, error: 'JSON inválido' });
  }

  const tokenEsperado = PropertiesService.getScriptProperties().getProperty('DASHBOARD_TOKEN');
  if (!tokenEsperado || body.token !== tokenEsperado) {
    return respuestaJson_({ ok: false, error: 'Token inválido' });
  }

  const fn = FUNCIONES_DISPONIBLES[body.funcion];
  if (!fn) {
    return respuestaJson_({ ok: false, error: 'Función no reconocida: ' + body.funcion });
  }

  try {
    ejecutarConControl_(body.funcion, fn);
    return respuestaJson_({ ok: true, proyecto: NOMBRE_PROYECTO, funcion: body.funcion });
  } catch (err) {
    return respuestaJson_({ ok: false, error: err.message });
  }
}

function respuestaJson_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
