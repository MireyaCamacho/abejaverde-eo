/**
 * ============================================================================
 *  AbejaVerde·EO — Motor de alertas v2 (Google Apps Script)
 *  Hoja: BD_AbejaVerde_EO  ·  Pestaña: Bitacora_Colmenas
 *
 *  Qué hace:
 *   1. Lee cada apiario de la bitácora (NDVI Copernicus + 3 preguntas).
 *   2. Calcula el SEMÁFORO con reglas fijas (Skill abejaverde-riesgo-apicola).
 *      Las reglas deciden el color: así el resultado es auditable y no cambia
 *      si la IA se equivoca.
 *   3. Pide a Gemini que redacte la acción recomendada (máx. 45 palabras).
 *      Si Gemini falla, usa una acción por defecto.
 *   4. Envía la alerta por el canal que eligió el apicultor:
 *      WhatsApp (WhatsApp Business Cloud API), Correo (Gmail/MailApp) o Ambos.
 *      Si WhatsApp falla, intenta por correo.
 *   5. Solo envía si el apicultor autorizó el tratamiento de sus datos
 *      (Ley 1581 de 2012). Registra fecha y resultado de cada envío.
 *
 *  Cómo empezar (una sola vez):
 *   Menú AbejaVerde·EO → 1. Preparar hoja → 2. Configurar claves
 *   → 3. Probar WhatsApp (hello_world) → 4. Evaluar y enviar alertas
 *   → 5. Programar envío semanal (opcional).
 * ============================================================================
 */

// ---------- Configuración general ----------
const HOJA = "Bitacora_Colmenas";
const MODELO_GEMINI = "gemini-2.5-flash";

// Columnas (base 1). Las columnas 1 a 11 son las del Manual Técnico Acelera Lab.
const COL = {
  ID: 1, MUNICIPIO: 2, GPS: 3, EMAIL: 4, NDVI: 5, CLIMA: 6,
  P1: 7, P2: 8, P3: 9, SEMAFORO: 10, ACCION: 11,
  // Columnas nuevas de la v2:
  WHATSAPP: 12, CANAL: 13, AUTORIZA: 14, FECHA_ALERTA: 15, ESTADO_ENVIO: 16
};
const ENCABEZADOS_V2 = [
  "Telefono_WhatsApp", "Canal_Preferido", "Autoriza_Datos_Ley1581",
  "Fecha_Ultima_Alerta", "Estado_Envio"
];

// Umbrales de NDVI de la Skill (ajustables tras el piloto).
const UMBRAL = { CRITICO: 0.35, BAJO: 0.50, OPTIMO: 0.60 };

const COLORES = {
  VERDE:    { fondo: "#8CC98C", texto: "Equilibrio óptimo" },
  AMARILLO: { fondo: "#F2C94C", texto: "Vigilancia operativa" },
  NARANJA:  { fondo: "#F2994A", texto: "Alerta preventiva" },
  ROJO:     { fondo: "#E06A5A", texto: "Riesgo crítico" }
};

// ============================================================================
//  MENÚ
// ============================================================================
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("AbejaVerde·EO")
    .addItem("1. Preparar hoja (columnas nuevas)", "prepararHoja")
    .addItem("2. Configurar claves (Gemini y WhatsApp)", "configurarClaves")
    .addItem("3. Probar WhatsApp (plantilla hello_world)", "probarWhatsApp")
    .addSeparator()
    .addItem("4. Evaluar y enviar alertas", "evaluarRiesgoApicolaYEnviarAlerta")
    .addItem("5. Programar envío semanal (lunes 7 a.m.)", "programarEnvioSemanal")
    .addToUi();
}

// ============================================================================
//  1. PREPARAR HOJA
// ============================================================================
function prepararHoja() {
  const sheet = obtenerHoja_();
  // Encabezados nuevos (no toca las columnas 1 a 11 del manual).
  sheet.getRange(1, COL.WHATSAPP, 1, ENCABEZADOS_V2.length).setValues([ENCABEZADOS_V2]);
  sheet.getRange(1, COL.WHATSAPP, 1, ENCABEZADOS_V2.length).setFontWeight("bold");

  const filas = Math.max(sheet.getMaxRows() - 1, 1);
  // Listas desplegables
  const reglaCanal = SpreadsheetApp.newDataValidation()
    .requireValueInList(["WhatsApp", "Correo", "Ambos"], true).build();
  const reglaAutoriza = SpreadsheetApp.newDataValidation()
    .requireValueInList(["SI", "NO"], true).build();
  sheet.getRange(2, COL.CANAL, filas, 1).setDataValidation(reglaCanal);
  sheet.getRange(2, COL.AUTORIZA, filas, 1).setDataValidation(reglaAutoriza);
  // El teléfono como texto, para que Sheets no lo convierta en número.
  sheet.getRange(2, COL.WHATSAPP, filas, 1).setNumberFormat("@");

  SpreadsheetApp.getUi().alert(
    "Hoja lista.\n\nComplete por cada apiario:\n" +
    "• Telefono_WhatsApp (ej. 3001234567)\n" +
    "• Canal_Preferido (WhatsApp, Correo o Ambos)\n" +
    "• Autoriza_Datos_Ley1581 (SI solo si el apicultor firmó la autorización)"
  );
}

// ============================================================================
//  2. CONFIGURAR CLAVES (se guardan en Propiedades del script, no en el código)
// ============================================================================
function configurarClaves() {
  const ui = SpreadsheetApp.getUi();
  const props = PropertiesService.getScriptProperties();
  const campos = [
    ["GEMINI_API_KEY", "API Key de Gemini (Google AI Studio)", ""],
    ["WA_TOKEN", "Token de acceso de WhatsApp Cloud API (Meta)", ""],
    ["WA_PHONE_NUMBER_ID", "Phone number ID de WhatsApp (Meta)", ""],
    ["WA_TEMPLATE", "Nombre de la plantilla aprobada", "alerta_semaforo_abejaverde"],
    ["WA_LANG", "Idioma de la plantilla", "es"],
    ["WA_GRAPH_VERSION", "Versión de la Graph API", "v23.0"]
  ];
  for (const [clave, etiqueta, porDefecto] of campos) {
    const actual = props.getProperty(clave);
    const pista = actual ? " (ya configurada; deje vacío para conservarla)" :
      (porDefecto ? ` (vacío = ${porDefecto})` : "");
    const r = ui.prompt("AbejaVerde·EO", etiqueta + pista, ui.ButtonSet.OK_CANCEL);
    if (r.getSelectedButton() !== ui.Button.OK) return;
    const valor = r.getResponseText().trim();
    if (valor) props.setProperty(clave, valor);
    else if (!actual && porDefecto) props.setProperty(clave, porDefecto);
  }
  ui.alert("Claves guardadas en las Propiedades del script.");
}

// ============================================================================
//  3. PRUEBA DE WHATSAPP con la plantilla hello_world (viene aprobada en Meta)
// ============================================================================
function probarWhatsApp() {
  const ui = SpreadsheetApp.getUi();
  const r = ui.prompt("Probar WhatsApp",
    "Número de destino (debe estar agregado como destinatario de prueba en Meta):",
    ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  const telefono = normalizarTelefono_(r.getResponseText());
  if (!telefono) { ui.alert("Número no válido."); return; }
  const res = llamarWhatsApp_({
    messaging_product: "whatsapp",
    to: telefono,
    type: "template",
    template: { name: "hello_world", language: { code: "en_US" } }
  });
  ui.alert(res.ok ? "Mensaje de prueba enviado a " + telefono : "Error: " + res.detalle);
}

// ============================================================================
//  4. MOTOR PRINCIPAL
// ============================================================================
function evaluarRiesgoApicolaYEnviarAlerta() {
  const sheet = obtenerHoja_();
  const datos = sheet.getDataRange().getValues();
  const resumen = { evaluados: 0, enviados: 0, sinAutorizacion: 0, errores: 0 };

  for (let i = 1; i < datos.length; i++) {
    const fila = datos[i];
    const idApiario = String(fila[COL.ID - 1] || "").trim();
    if (!idApiario) continue;

    const municipio = String(fila[COL.MUNICIPIO - 1] || "").trim();
    const email = String(fila[COL.EMAIL - 1] || "").trim();
    const ndvi = leerNumero_(fila[COL.NDVI - 1]);
    const clima = String(fila[COL.CLIMA - 1] || "");
    const p1 = nivelPoblacion_(fila[COL.P1 - 1]);
    const p2 = nivelReservas_(fila[COL.P2 - 1]);
    const p3 = estadoReina_(fila[COL.P3 - 1]);
    const filaHoja = i + 1;

    if (isNaN(ndvi)) {
      escribirEstado_(sheet, filaHoja, "Sin dato NDVI válido: no se evaluó");
      resumen.errores++;
      continue;
    }

    // a) Semáforo por reglas
    const semaforo = calcularSemaforo_(ndvi, p1, p2, p3, clima);
    // b) Acción redactada por Gemini (con respaldo)
    const accion = redactarAccion_(semaforo, municipio, ndvi, clima, p1, p2, p3);

    sheet.getRange(filaHoja, COL.SEMAFORO).setValue(semaforo)
      .setBackground(COLORES[semaforo].fondo);
    sheet.getRange(filaHoja, COL.ACCION).setValue(accion);
    resumen.evaluados++;

    // c) Envío según canal y autorización
    const autoriza = String(fila[COL.AUTORIZA - 1] || "").trim().toUpperCase() === "SI";
    if (!autoriza) {
      escribirEstado_(sheet, filaHoja, "No enviado: falta autorización Ley 1581");
      resumen.sinAutorizacion++;
      continue;
    }

    const canal = normalizarCanal_(fila[COL.CANAL - 1], fila[COL.WHATSAPP - 1], email);
    const telefono = normalizarTelefono_(fila[COL.WHATSAPP - 1]);
    const resultados = [];
    let enviado = false;

    if (canal === "WHATSAPP" || canal === "AMBOS") {
      const wa = telefono
        ? enviarWhatsApp_(telefono, idApiario, municipio, semaforo, accion)
        : { ok: false, detalle: "sin teléfono válido" };
      resultados.push("WhatsApp: " + (wa.ok ? "OK" : "falló (" + wa.detalle + ")"));
      enviado = enviado || wa.ok;
      // Respaldo: si WhatsApp falla y el canal era solo WhatsApp, intenta correo.
      if (!wa.ok && canal === "WHATSAPP" && esEmail_(email)) {
        const c = enviarCorreo_(email, idApiario, municipio, ndvi, semaforo, accion);
        resultados.push("Correo (respaldo): " + (c.ok ? "OK" : "falló (" + c.detalle + ")"));
        enviado = enviado || c.ok;
      }
    }
    if (canal === "CORREO" || canal === "AMBOS") {
      const c = esEmail_(email)
        ? enviarCorreo_(email, idApiario, municipio, ndvi, semaforo, accion)
        : { ok: false, detalle: "sin correo válido" };
      resultados.push("Correo: " + (c.ok ? "OK" : "falló (" + c.detalle + ")"));
      enviado = enviado || c.ok;
    }
    if (canal === "NINGUNO") resultados.push("Sin teléfono ni correo válidos");

    escribirEstado_(sheet, filaHoja, resultados.join(" · "));
    if (enviado) {
      sheet.getRange(filaHoja, COL.FECHA_ALERTA).setValue(new Date());
      resumen.enviados++;
    } else {
      resumen.errores++;
    }
  }

  const msg = `Evaluados: ${resumen.evaluados} · Alertas enviadas: ${resumen.enviados} · ` +
              `Sin autorización: ${resumen.sinAutorizacion} · Con errores: ${resumen.errores}`;
  Logger.log(msg);
  try { SpreadsheetApp.getUi().alert(msg); } catch (e) { /* ejecución por activador: sin interfaz */ }
}

// ============================================================================
//  REGLAS DEL SEMÁFORO (Skill abejaverde-riesgo-apicola, cubriendo todos los casos)
// ============================================================================
function calcularSemaforo_(ndvi, p1, p2, p3, clima) {
  const lluviaIntensa = /lluvi/i.test(clima) && /(intens|fuert|torrenc|persist)/i.test(clima);

  // ROJO: sin floración, muchas bocas y reservas bajas (o reina detenida).
  if (ndvi < UMBRAL.CRITICO && p2 === "BAJA" && (p1 !== "BAJA" || p3 === "INACTIVA")) return "ROJO";
  // NARANJA: territorio en crisis pero la colmena aún tiene reservas = cuenta regresiva.
  if (ndvi < UMBRAL.CRITICO) return "NARANJA";
  // NARANJA: floración baja con reservas bajas o postura detenida.
  if (ndvi < UMBRAL.BAJO && (p2 === "BAJA" || p3 === "INACTIVA")) return "NARANJA";
  // NARANJA: lluvias intensas que impiden el pecoreo.
  if (lluviaIntensa) return "NARANJA";
  // AMARILLO: hay flores pero la colmena está débil (problema local).
  if (p1 === "BAJA" || p2 === "BAJA" || p3 === "INACTIVA") return "AMARILLO";
  // AMARILLO: colmena bien, pero floración todavía por debajo del óptimo.
  if (ndvi < UMBRAL.OPTIMO) return "AMARILLO";
  // VERDE: buena floración, buenas reservas y reina activa.
  return "VERDE";
}

function nivelPoblacion_(v) {
  const t = String(v || "").toLowerCase();
  if (t.includes("alta") || t.includes("fuerte")) return "ALTA";
  if (t.includes("media") || t.includes("normal")) return "MEDIA";
  if (t.includes("baja") || t.includes("débil") || t.includes("debil")) return "BAJA";
  return "MEDIA";
}
function nivelReservas_(v) {
  const t = String(v || "").toLowerCase();
  if (t.includes("baja") || t.includes("vací") || t.includes("vaci")) return "BAJA";
  if (t.includes("alta") || t.includes("llena")) return "ALTA";
  return "MEDIA";
}
function estadoReina_(v) {
  const t = String(v || "").toLowerCase();
  if (t.includes("inactiva") || t.includes("detenida") || t.includes("sin") || t.includes("no ")) return "INACTIVA";
  return "ACTIVA";
}

// ============================================================================
//  GEMINI: redacta la acción (el color ya está decidido por las reglas)
// ============================================================================
function redactarAccion_(semaforo, municipio, ndvi, clima, p1, p2, p3) {
  const apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");
  if (!apiKey) return accionPorDefecto_(semaforo);

  const prompt =
    `Actúa según la Skill abejaverde-riesgo-apicola. El semáforo YA está decidido: ${semaforo}.\n` +
    `Datos: municipio ${municipio}; NDVI Copernicus ${ndvi}; clima "${clima}"; ` +
    `población ${p1}; reservas de miel y polen ${p2}; postura de la reina ${p3}.\n` +
    `Redacta UNA acción práctica para el apicultor esta semana, en español sencillo de Colombia, ` +
    `máximo 45 palabras, con dosis o manejo concreto (ej. jarabe 1:1, torta proteica, ` +
    `reducir piquera, colocar alza). Sin saltos de línea. ` +
    `Devuelve JSON estricto: {"accion_recomendada": "..."}`;

  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODELO_GEMINI}:generateContent?key=${apiKey}`;
    const resp = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      muteHttpExceptions: true,
      payload: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { responseMimeType: "application/json", temperature: 0.3 }
      })
    });
    if (resp.getResponseCode() !== 200) return accionPorDefecto_(semaforo);
    const texto = JSON.parse(resp.getContentText()).candidates[0].content.parts[0].text;
    const accion = String(JSON.parse(texto).accion_recomendada || "").trim();
    return accion ? recortarPalabras_(accion, 45) : accionPorDefecto_(semaforo);
  } catch (e) {
    Logger.log("Gemini no respondió: " + e);
    return accionPorDefecto_(semaforo);
  }
}

function accionPorDefecto_(semaforo) {
  return {
    ROJO: "Alimente hoy con jarabe de azúcar 1:1 (1 litro por colmena) y torta proteica; asegure agua limpia cerca y revise en 48 horas. Si necesita apoyo, avise al técnico.",
    NARANJA: "La floración está bajando: prepare jarabe 1:1 y torta proteica para la próxima visita, revise reservas en cada colmena y asegure agua cerca del apiario.",
    AMARILLO: "Hay flores, pero la colmena está débil: revise la postura de la reina y la sanidad de la cría, reduzca la piquera si hace frío y una colmenas débiles si es necesario.",
    VERDE: "Todo en orden: mantenga la revisión habitual y evalúe colocar alza melaria si los cuadros de miel están llenos."
  }[semaforo];
}

// ============================================================================
//  WHATSAPP (WhatsApp Business Cloud API de Meta)
//  Fuera de la ventana de 24 horas, Meta solo permite enviar PLANTILLAS aprobadas.
//  Plantilla sugerida "alerta_semaforo_abejaverde" (categoría Utilidad, español):
//    AbejaVerde·EO – Apiario {{1}} ({{2}}). Semáforo: {{3}}.
//    Acción recomendada esta semana: {{4}}
//    Si necesita apoyo, comuníquese con su técnico de AbejaVerde.
// ============================================================================
function enviarWhatsApp_(telefono, idApiario, municipio, semaforo, accion) {
  const props = PropertiesService.getScriptProperties();
  return llamarWhatsApp_({
    messaging_product: "whatsapp",
    to: telefono,
    type: "template",
    template: {
      name: props.getProperty("WA_TEMPLATE") || "alerta_semaforo_abejaverde",
      language: { code: props.getProperty("WA_LANG") || "es" },
      components: [{
        type: "body",
        parameters: [
          { type: "text", text: limpiarParametro_(idApiario) },
          { type: "text", text: limpiarParametro_(municipio || "Cundinamarca") },
          { type: "text", text: semaforo + " – " + COLORES[semaforo].texto },
          { type: "text", text: limpiarParametro_(accion) }
        ]
      }]
    }
  });
}

function llamarWhatsApp_(payload) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty("WA_TOKEN");
  const phoneId = props.getProperty("WA_PHONE_NUMBER_ID");
  const version = props.getProperty("WA_GRAPH_VERSION") || "v23.0";
  if (!token || !phoneId) return { ok: false, detalle: "faltan WA_TOKEN o WA_PHONE_NUMBER_ID" };
  try {
    const resp = UrlFetchApp.fetch(`https://graph.facebook.com/${version}/${phoneId}/messages`, {
      method: "post",
      contentType: "application/json",
      headers: { Authorization: "Bearer " + token },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    const codigo = resp.getResponseCode();
    if (codigo >= 200 && codigo < 300) return { ok: true, detalle: "" };
    let detalle = "HTTP " + codigo;
    try { detalle += " " + JSON.parse(resp.getContentText()).error.message; } catch (e) {}
    return { ok: false, detalle: detalle.slice(0, 180) };
  } catch (e) {
    return { ok: false, detalle: String(e).slice(0, 180) };
  }
}

// ============================================================================
//  CORREO (Gmail / MailApp)
// ============================================================================
function enviarCorreo_(email, idApiario, municipio, ndvi, semaforo, accion) {
  try {
    const c = COLORES[semaforo];
    const html =
      `<div style="font-family:Arial,sans-serif;max-width:560px">` +
      `<h2 style="color:#1F3A2B;margin:0 0 8px">AbejaVerde·EO</h2>` +
      `<p style="margin:0 0 12px">Apiario <b>${idApiario}</b> (${municipio})</p>` +
      `<div style="background:${c.fondo};padding:14px 18px;border-radius:10px;font-size:18px">` +
      `<b>Semáforo ${semaforo}</b> – ${c.texto}</div>` +
      `<p style="margin:16px 0 4px"><b>Acción recomendada esta semana:</b></p>` +
      `<p style="margin:0 0 16px">${accion}</p>` +
      `<p style="color:#555;font-size:13px">Dato satelital Copernicus (NDVI del entorno): ${ndvi}</p>` +
      `<hr><p style="color:#777;font-size:12px">Recibe este mensaje porque autorizó el tratamiento ` +
      `de sus datos para alertas apícolas (Ley 1581 de 2012). Para dejar de recibirlas, responda ` +
      `este correo con la palabra BAJA.</p></div>`;
    MailApp.sendEmail({
      to: email,
      subject: `[AbejaVerde·EO] Semáforo ${semaforo} – Apiario ${idApiario} (${municipio})`,
      body: `AbejaVerde·EO\nApiario ${idApiario} (${municipio})\nSemáforo: ${semaforo} – ${c.texto}\n` +
            `Acción recomendada esta semana: ${accion}\nNDVI Copernicus: ${ndvi}`,
      htmlBody: html,
      name: "AbejaVerde·EO"
    });
    return { ok: true, detalle: "" };
  } catch (e) {
    return { ok: false, detalle: String(e).slice(0, 180) };
  }
}

// ============================================================================
//  5. ACTIVADOR SEMANAL
// ============================================================================
function programarEnvioSemanal() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === "evaluarRiesgoApicolaYEnviarAlerta")
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger("evaluarRiesgoApicolaYEnviarAlerta")
    .timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(7).create();
  SpreadsheetApp.getUi().alert("Listo: las alertas se evaluarán y enviarán cada lunes a las 7 a.m.");
}

// ============================================================================
//  UTILIDADES
// ============================================================================
function obtenerHoja_() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(HOJA);
  if (!sheet) throw new Error(`No existe la pestaña "${HOJA}".`);
  return sheet;
}
function escribirEstado_(sheet, fila, texto) {
  sheet.getRange(fila, COL.ESTADO_ENVIO).setValue(texto);
}
function leerNumero_(v) {
  if (typeof v === "number") return v;
  // Acepta "0.28", "0,28", "0. 28 (Floración Muy Baja)"
  const m = String(v || "").replace(/\s+/g, "").replace(",", ".").match(/-?\d+(\.\d+)?/);
  return m ? parseFloat(m[0]) : NaN;
}
function normalizarTelefono_(v) {
  let d = String(v || "").replace(/\D/g, "");
  if (d.length === 10 && d.startsWith("3")) d = "57" + d;   // celular colombiano
  return d.length >= 11 && d.length <= 15 ? d : "";
}
function esEmail_(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(v || "").trim());
}
function normalizarCanal_(canal, telefono, email) {
  const t = String(canal || "").toLowerCase();
  if (t.startsWith("amb")) return "AMBOS";
  if (t.startsWith("what") || t === "wp" || t === "wa") return "WHATSAPP";
  if (t.startsWith("corr") || t.startsWith("mail") || t.startsWith("email")) return "CORREO";
  // Sin canal elegido: WhatsApp si hay teléfono, si no correo.
  if (normalizarTelefono_(telefono)) return "WHATSAPP";
  if (esEmail_(email)) return "CORREO";
  return "NINGUNO";
}
function limpiarParametro_(t) {
  // Meta no admite saltos de línea, tabulaciones ni más de 4 espacios seguidos en parámetros.
  return String(t || "").replace(/[\n\r\t]+/g, " ").replace(/ {2,}/g, " ").trim().slice(0, 900);
}
function recortarPalabras_(t, max) {
  const p = String(t).replace(/[\n\r]+/g, " ").split(/\s+/);
  return p.length <= max ? p.join(" ") : p.slice(0, max).join(" ") + "…";
}
