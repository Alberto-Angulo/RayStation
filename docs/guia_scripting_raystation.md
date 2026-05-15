# Guía paso a paso: empezar con Python Scripting en RayStation

Esta guía está pensada para un primer flujo clínico/técnico en **RayStation** usando scripting con Python (normalmente IronPython dentro de RayStation).

> Objetivo inicial: obtener métricas típicas de conformación en radiocirugía (SRS/SRT), permitiendo seleccionar uno o varios PTV desde una ventana.

---

## 1) Preparación del entorno

1. Abrir un paciente de prueba (no empezar en un caso clínico real).
2. Cargar un plan con:
   - PTV definido
   - Dosis calculada
   - Prescripción establecida
3. Abrir la consola de scripting en RayStation:
   - `Scripting` → `Script Editor` (el nombre puede variar según versión)
4. Verificar acceso a objetos principales (`Patient`, `Case`, `Plan`, `BeamSet`).

---

## 2) Métricas que calcula el script mejorado

Para cada PTV seleccionado (y para unión de PTVs si eliges varios):

- **TV**: volumen del PTV.
- **PIV100**: volumen de la isodosis al 100% de prescripción.
- **TV_PIV100**: intersección entre PTV e isodosis de prescripción.
- **PIV50**: volumen de la isodosis al 50% de prescripción.

Con estos volúmenes:

- **Índice de cobertura** = `TV_PIV100 / TV`
- **Selectividad** = `TV_PIV100 / PIV100`
- **Índice de Paddick** = `(TV_PIV100^2) / (TV * PIV100)`
- **Índice de gradiente (GI)** = `PIV50 / PIV100`
- **Índice de conformidad RTOG (CI_RTOG)** = `PIV100 / TV`
- **Quality of Coverage (QoC)** = `Dmin_target / Dosis_prescrita`
- **Índice de homogeneidad (HI)** = `Dmax_target / Dosis_prescrita`
- **New Conformity Index (NCI)** = `(TV * PIV100) / (TV_PIV100^2)`

---

## 3) Flujo del script

1. Detecta ROIs cuyo nombre empieza con `PTV`.
2. Abre una ventana para seleccionar uno o varios PTV (intenta primero Windows Forms; si no está disponible usa tkinter; si no hay GUI, selecciona todos automáticamente).
3. Genera dos ROIs de isodosis desde dosis total del plan:
   - `Iso_Rx_100` (prescripción)
   - `Iso_Rx_50` (50% de prescripción)
4. Para cada PTV, crea ROI temporal de intersección con `Iso_Rx_100`.
5. Calcula cobertura, selectividad, Paddick y GI, y los muestra en consola + ventana de resultados.
6. Si hay varios PTV, también calcula métricas sobre la **unión de PTVs**.

---

## 4) Script

Usa `scripts/ejemplo_metricas_conformacion.py`.

> Nota importante: algunos métodos de API (por ejemplo álgebra de ROI o creación de ROI desde dosis) pueden variar ligeramente entre versiones de RayStation.
>
> Compatibilidad GUI: el script intenta `System.Windows.Forms` (entorno .NET/IronPython). Si falla (por ejemplo en CPython con error `No module named System.Windows.Forms`), usa `tkinter`. Si tampoco está disponible, continúa seleccionando todos los PTV.
> Compatibilidad de prescripción: el script intenta leer la dosis Rx con varias rutas de API (`PrimaryDosePrescription`, `PrimaryPrescriptionDoseReference`, `PrescriptionDoseReferences`) para evitar errores de versión como `Object has no member PrimaryDosePrescription`.


---

## 4.1) Estilo visual de ventanas

- El selector de PTV y la ventana de resultados usan tema hospitalario:
  - Fondo azul celeste suave
  - Paneles blancos
  - Botones de acción en azul celeste

---

## 5) Verificación rápida (checklist)

- [ ] Aparece ventana de selección (WinForms o tkinter).
- [ ] Se generan/actualizan `Iso_Rx_100` e `Iso_Rx_50`.
- [ ] Se imprimen índices principales: cobertura, selectividad, Paddick, GI, RTOG CI, QoC, HI y NCI.
- [ ] También aparece ventana de resultados con el resumen completo.
- [ ] Los valores son clínicamente plausibles según protocolo local.

---

## 6) Recomendaciones clínicas/técnicas

1. Validar en varios casos test contra cálculo manual o referencia.
2. Definir en protocolo local si reportar por lesión, por PTV o combinado.
3. Si se desea limpieza automática, eliminar ROIs temporales al final.
4. Añadir exportación a CSV para auditoría y QA.



## 7) Otros índices relevantes en este ámbito

Según protocolo del centro, también suele ser útil añadir:

- **V12Gy** (SRS cerebral): predictor de riesgo de radionecrosis.
- **D2% / D98% / D50%** en target para caracterizar heterogeneidad y cobertura.
- **Paddick Gradient Measure (PGM)** o métricas de caída de dosis.
- **Dmáx/D0.03cc en OARs críticos** (tronco, quiasma, nervio óptico, etc.).

Estos pueden integrarse en una siguiente iteración del script.

## 8) Ideas de scripts más complejos (siguiente nivel)

¡Excelente pregunta! En radioterapia hay muchísimo potencial de automatización avanzada.

### A) QA dosimétrico automatizado por protocolo
- Leer objetivo/prescripción/técnica y evaluar reglas del centro.
- Validar métricas target + OAR automáticamente.
- Generar semáforo (OK / advertencia / bloqueo) y reporte en PDF/CSV.

### B) Auto-contouring + postprocesado inteligente
- Ejecutar segmentación automática.
- Aplicar limpieza geométrica (agujeros, artefactos, continuidad).
- Verificar volumen y posición vs atlas/casos históricos.

### C) Planning assistant (plantillas inteligentes)
- Crear objetivos de optimización en función de localización, tamaño y distancia a OAR.
- Ajustar prioridades/pesos automáticamente por iteraciones.
- Recomendar técnica (VMAT/IMRT/SRS/SBRT) según reglas clínicas.

### D) Adaptative RT workflow
- Comparar anatomía diaria (CBCT/CT de control) vs planificación.
- Recalcular DVH y detectar degradación de cobertura/OAR.
- Sugerir automáticamente criterio de replan.

### E) Batch analytics y minería de datos
- Analizar cientos de planes para benchmark interno.
- Curvas de aprendizaje por equipo/técnica.
- Detección de outliers de calidad o eficiencia.

### F) Automatización de reportes clínicos completos
- Unir métricas dosimétricas, geometría, dosis por fracción y constraints.
- Exportar informe estructurado para comité/tumor board.
- Integración con R&V / PACS / data warehouse del hospital.

### G) Scripts de seguridad y consistencia
- Comprobaciones pre-tratamiento (nomenclatura, coordenadas, isocentro, colisiones).
- Verificación independiente de MU/rangos de parámetros.
- Alertas tempranas ante configuraciones inusuales.

### H) Modelos predictivos (proyecto avanzado)
- Predicción de toxicidad a partir de DVH + variables clínicas.
- Recomendación de constraints personalizados por paciente.
- Score de complejidad y riesgo antes de aprobar el plan.

---

### Recomendación práctica
Si quieres, el siguiente script que más valor suele dar rápido en clínica es:

1. **QA automático por protocolo + reporte semáforo**, y luego
2. **Export masivo de métricas para analítica histórica**.

Con eso obtienes impacto inmediato en seguridad, estandarización y tiempo.
