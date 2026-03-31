"""Script de ejemplo para métricas de conformación en RayStation (SRS/SRT).

Incluye:
- Selección de uno o varios PTV (con fallback si no hay WinForms)
- Cálculo de cobertura, selectividad, índice de Paddick e índice de gradiente

Nota: la API exacta de RayStation puede variar según versión.
"""

from connect import get_current

COLOR_BG = "#EAF6FF"
COLOR_PANEL = "#FFFFFF"
COLOR_ACCENT = "#4AA3DF"
COLOR_TEXT = "#0B2A42"


def _zero_margin():
    return {
        "Type": "Expand",
        "Superior": 0,
        "Inferior": 0,
        "Anterior": 0,
        "Posterior": 0,
        "Right": 0,
        "Left": 0,
    }


def ensure_roi(case, roi_name, color="Yellow", roi_type="Control"):
    existing = [r.Name for r in case.PatientModel.RegionsOfInterest]
    if roi_name not in existing:
        case.PatientModel.CreateRoi(Name=roi_name, Color=color, Type=roi_type)


def get_roi_geometry(case, exam, roi_name):
    ss = case.PatientModel.StructureSets[exam.Name]
    for rg in ss.RoiGeometries:
        if rg.OfRoi.Name == roi_name:
            return rg
    return None


def get_roi_volume_cc(case, exam, roi_name):
    rg = get_roi_geometry(case, exam, roi_name)
    if rg is None or not rg.HasContours():
        return None
    return rg.GetRoiVolume()


def create_isodose_roi(case, plan, roi_name, threshold_cgy, color="Yellow"):
    ensure_roi(case, roi_name, color=color, roi_type="Control")
    case.PatientModel.RegionsOfInterest[roi_name].CreateRoiGeometryFromDose(
        DoseDistribution=plan.TreatmentCourse.TotalDose,
        ThresholdLevel=threshold_cgy,
    )


def create_intersection_roi(case, exam, roi_name, roi_a, roi_b, color="Magenta"):
    ensure_roi(case, roi_name, color=color, roi_type="Control")
    roi = case.PatientModel.RegionsOfInterest[roi_name]
    roi.SetAlgebraExpression(
        ExpressionA={
            "Operation": "Union",
            "SourceRoiNames": [roi_a],
            "MarginSettings": _zero_margin(),
        },
        ExpressionB={
            "Operation": "Union",
            "SourceRoiNames": [roi_b],
            "MarginSettings": _zero_margin(),
        },
        ResultOperation="Intersection",
        ResultMarginSettings=_zero_margin(),
    )
    roi.UpdateDerivedGeometry(Examination=exam, Algorithm="Auto")


def create_union_roi(case, exam, roi_name, roi_names, color="Cyan"):
    ensure_roi(case, roi_name, color=color, roi_type="Control")
    roi = case.PatientModel.RegionsOfInterest[roi_name]
    roi.SetAlgebraExpression(
        ExpressionA={
            "Operation": "Union",
            "SourceRoiNames": roi_names,
            "MarginSettings": _zero_margin(),
        },
        ExpressionB={
            "Operation": "Union",
            "SourceRoiNames": [],
            "MarginSettings": _zero_margin(),
        },
        ResultOperation="None",
        ResultMarginSettings=_zero_margin(),
    )
    roi.UpdateDerivedGeometry(Examination=exam, Algorithm="Auto")


def _select_ptvs_winforms(ptv_candidates):
    from System.Drawing import Color, ColorTranslator
    from System.Windows.Forms import (
        Application,
        Button,
        CheckedListBox,
        DialogResult,
        Form,
        FormStartPosition,
        Label,
    )

    Application.EnableVisualStyles()

    bg = ColorTranslator.FromHtml(COLOR_BG)
    panel = ColorTranslator.FromHtml(COLOR_PANEL)
    accent = ColorTranslator.FromHtml(COLOR_ACCENT)
    text_color = ColorTranslator.FromHtml(COLOR_TEXT)

    form = Form()
    form.Text = "Seleccionar PTV(s)"
    form.Width = 420
    form.Height = 420
    form.StartPosition = FormStartPosition.CenterScreen
    form.BackColor = bg

    label = Label()
    label.Text = "Selecciona uno o varios PTV para calcular métricas:"
    label.Left = 10
    label.Top = 10
    label.Width = 380
    label.ForeColor = text_color
    label.BackColor = bg
    form.Controls.Add(label)

    clb = CheckedListBox()
    clb.Left = 10
    clb.Top = 35
    clb.Width = 380
    clb.Height = 280
    clb.BackColor = panel
    clb.ForeColor = text_color
    for name in ptv_candidates:
        clb.Items.Add(name, True)
    form.Controls.Add(clb)

    btn_ok = Button()
    btn_ok.Text = "Aceptar"
    btn_ok.Left = 220
    btn_ok.Top = 330
    btn_ok.DialogResult = DialogResult.OK
    btn_ok.BackColor = accent
    btn_ok.ForeColor = panel
    form.Controls.Add(btn_ok)

    btn_cancel = Button()
    btn_cancel.Text = "Cancelar"
    btn_cancel.Left = 310
    btn_cancel.Top = 330
    btn_cancel.DialogResult = DialogResult.Cancel
    btn_cancel.BackColor = panel
    btn_cancel.ForeColor = text_color
    form.Controls.Add(btn_cancel)

    form.AcceptButton = btn_ok
    form.CancelButton = btn_cancel

    selected = []
    if form.ShowDialog() == DialogResult.OK:
        for item in clb.CheckedItems:
            selected.append(str(item))

    form.Dispose()
    return selected


def _select_ptvs_tkinter(ptv_candidates):
    import tkinter as tk

    root = tk.Tk()
    root.title("Seleccionar PTV(s)")
    root.geometry("440x460")
    root.configure(bg=COLOR_BG)

    tk.Label(root, text="Selecciona uno o varios PTV para calcular métricas:", bg=COLOR_BG, fg=COLOR_TEXT).pack(pady=8)

    listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, width=45, height=15, bg=COLOR_PANEL, fg=COLOR_TEXT, selectbackground=COLOR_ACCENT, selectforeground=COLOR_PANEL)
    for name in ptv_candidates:
        listbox.insert(tk.END, name)
    listbox.pack(pady=8)

    for i in range(len(ptv_candidates)):
        listbox.selection_set(i)

    result = {"selected": []}

    def accept():
        result["selected"] = [ptv_candidates[i] for i in listbox.curselection()]
        root.destroy()

    def cancel():
        result["selected"] = []
        root.destroy()

    button_frame = tk.Frame(root, bg=COLOR_BG)
    button_frame.pack(pady=10)
    tk.Button(button_frame, text="Aceptar", command=accept, width=12, bg=COLOR_ACCENT, fg=COLOR_PANEL, activebackground=COLOR_ACCENT, activeforeground=COLOR_PANEL).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Cancelar", command=cancel, width=12, bg=COLOR_PANEL, fg=COLOR_TEXT).pack(side=tk.LEFT, padx=5)

    root.mainloop()
    return result["selected"]


def select_ptvs(ptv_candidates):
    # 1) Intentar WinForms (entorno típico IronPython/.NET)
    try:
        return _select_ptvs_winforms(ptv_candidates)
    except Exception as err_winforms:
        print("[INFO] WinForms no disponible: {0}".format(err_winforms))

    # 2) Intentar tkinter (entorno CPython)
    try:
        return _select_ptvs_tkinter(ptv_candidates)
    except Exception as err_tk:
        print("[INFO] tkinter no disponible: {0}".format(err_tk))

    # 3) Fallback seguro: seleccionar todos y continuar
    print("[WARN] No hay librería GUI disponible. Se seleccionarán todos los PTV automáticamente.")
    return list(ptv_candidates)




def _safe_get_attr(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception:
        return None


def _extract_dose_value(candidate):
    if candidate is None:
        return None
    dose = _safe_get_attr(candidate, "DoseValue")
    if dose is not None:
        return dose
    # Algunas versiones usan DosePrescription o campos anidados
    dose_presc = _safe_get_attr(candidate, "DosePrescription")
    if dose_presc is not None:
        nested = _safe_get_attr(dose_presc, "DoseValue")
        if nested is not None:
            return nested
    return None


def get_prescription_dose_cgy(beam_set):
    """Obtiene dosis de prescripción en cGy con compatibilidad entre versiones."""
    prescription = _safe_get_attr(beam_set, "Prescription")
    if prescription is None:
        raise RuntimeError("BeamSet no contiene objeto Prescription.")

    # Ruta moderna/alternativa 1
    for attr in ["PrimaryDosePrescription", "PrimaryPrescriptionDoseReference"]:
        ref = _safe_get_attr(prescription, attr)
        dose = _extract_dose_value(ref)
        if dose is not None:
            return dose

    # Ruta alternativa 2: lista de referencias
    refs = _safe_get_attr(prescription, "PrescriptionDoseReferences")
    if refs is not None:
        try:
            for ref in refs:
                dose = _extract_dose_value(ref)
                if dose is not None:
                    return dose
        except Exception:
            pass

    # Ruta alternativa 3: dose directa en Prescription
    dose_direct = _extract_dose_value(prescription)
    if dose_direct is not None:
        return dose_direct

    raise RuntimeError(
        "No se pudo leer la dosis de prescripción del BeamSet. "
        "Revisa la API de tu versión (p.ej. PrimaryPrescriptionDoseReference o PrescriptionDoseReferences)."
    )




def _show_results_winforms(results_text):
    from System.Drawing import Color, ColorTranslator
    from System.Windows.Forms import Application, Button, Form, FormStartPosition, TextBox, ScrollBars

    Application.EnableVisualStyles()

    bg = ColorTranslator.FromHtml(COLOR_BG)
    panel = ColorTranslator.FromHtml(COLOR_PANEL)
    accent = ColorTranslator.FromHtml(COLOR_ACCENT)
    text_color = ColorTranslator.FromHtml(COLOR_TEXT)

    form = Form()
    form.Text = "Resultados de métricas SRS/SRT"
    form.Width = 760
    form.Height = 560
    form.StartPosition = FormStartPosition.CenterScreen
    form.BackColor = bg

    textbox = TextBox()
    textbox.Multiline = True
    textbox.ReadOnly = True
    textbox.ScrollBars = ScrollBars.Vertical
    textbox.Left = 12
    textbox.Top = 12
    textbox.Width = 720
    textbox.Height = 470
    textbox.BackColor = panel
    textbox.ForeColor = text_color
    textbox.Text = results_text
    form.Controls.Add(textbox)

    btn_close = Button()
    btn_close.Text = "Cerrar"
    btn_close.Left = 640
    btn_close.Top = 490
    btn_close.Width = 90
    btn_close.BackColor = accent
    btn_close.ForeColor = panel
    btn_close.DialogResult = 1
    form.Controls.Add(btn_close)

    form.AcceptButton = btn_close
    form.ShowDialog()
    form.Dispose()


def _show_results_tkinter(results_text):
    import tkinter as tk

    root = tk.Tk()
    root.title("Resultados de métricas SRS/SRT")
    root.geometry("780x600")
    root.configure(bg=COLOR_BG)

    txt = tk.Text(root, wrap=tk.WORD, bg=COLOR_PANEL, fg=COLOR_TEXT)
    txt.insert("1.0", results_text)
    txt.configure(state=tk.DISABLED)
    txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    tk.Button(
        root,
        text="Cerrar",
        command=root.destroy,
        bg=COLOR_ACCENT,
        fg=COLOR_PANEL,
        activebackground=COLOR_ACCENT,
        activeforeground=COLOR_PANEL,
        width=12,
    ).pack(pady=8)

    root.mainloop()


def show_results(results_text):
    try:
        _show_results_winforms(results_text)
        return
    except Exception as err_winforms:
        print("[INFO] Ventana de resultados WinForms no disponible: {0}".format(err_winforms))

    try:
        _show_results_tkinter(results_text)
        return
    except Exception as err_tk:
        print("[INFO] Ventana de resultados tkinter no disponible: {0}".format(err_tk))

    print("\n[INFO] Mostrando resultados en consola (sin GUI disponible):\n")
    print(results_text)



def _get_dose_statistic(total_dose, roi_name, dose_type):
    """Intenta recuperar estadístico de dosis (Min/Max) con tolerancia de API."""
    # Firma más habitual en varias versiones
    try:
        return total_dose.GetDoseStatistic(RoiName=roi_name, DoseType=dose_type)
    except Exception:
        pass

    # Variantes posibles de mayúsculas/minúsculas
    for dt in [dose_type.lower(), dose_type.upper(), dose_type.capitalize()]:
        try:
            return total_dose.GetDoseStatistic(RoiName=roi_name, DoseType=dt)
        except Exception:
            pass

    return None


def compute_extended_metrics(tv_vol, piv_vol, tv_piv_vol, piv50_vol, rx_cgy, dmin_cgy, dmax_cgy):
    # Métricas ya usadas
    coverage = (tv_piv_vol / tv_vol) if tv_vol and tv_vol > 0 else None
    selectivity = (tv_piv_vol / piv_vol) if piv_vol and piv_vol > 0 else None
    paddick = (
        (tv_piv_vol * tv_piv_vol) / (tv_vol * piv_vol)
        if tv_vol and piv_vol and tv_vol > 0 and piv_vol > 0
        else None
    )
    gradient_index = (piv50_vol / piv_vol) if piv50_vol and piv_vol and piv_vol > 0 else None

    # 1) Índice de conformidad RTOG
    rtog_ci = (piv_vol / tv_vol) if piv_vol and tv_vol and tv_vol > 0 else None

    # 2) Quality of Coverage (QoC)
    # Definición habitual RTOG: dosis mínima en el target / dosis prescrita
    qoc = (dmin_cgy / rx_cgy) if dmin_cgy and rx_cgy and rx_cgy > 0 else None

    # 3) Índice de homogeneidad (HI)
    # Definición simple SRS frecuente: Dmax / Dpresc
    hi = (dmax_cgy / rx_cgy) if dmax_cgy and rx_cgy and rx_cgy > 0 else None

    # 4) New Conformity Index (NCI)
    # NCI = (TV * PIV) / (TV_PIV)^2 = 1 / Paddick
    nci = (
        (tv_vol * piv_vol) / (tv_piv_vol * tv_piv_vol)
        if tv_vol and piv_vol and tv_piv_vol and tv_piv_vol > 0
        else None
    )

    return {
        "coverage": coverage,
        "selectivity": selectivity,
        "paddick": paddick,
        "gradient_index": gradient_index,
        "rtog_ci": rtog_ci,
        "qoc": qoc,
        "hi": hi,
        "nci": nci,
    }
def print_metrics(title, tv_vol, piv_vol, tv_piv_vol, piv50_vol, rx_cgy, dmin_cgy, dmax_cgy):
    metrics = compute_extended_metrics(
        tv_vol, piv_vol, tv_piv_vol, piv50_vol, rx_cgy, dmin_cgy, dmax_cgy
    )

    lines = []
    lines.append("=== {0} ===".format(title))
    lines.append("TV (PTV) [cc]: {0}".format(round(tv_vol, 3) if tv_vol is not None else "N/A"))
    lines.append("PIV100 [cc]: {0}".format(round(piv_vol, 3) if piv_vol is not None else "N/A"))
    lines.append("TV_PIV100 [cc]: {0}".format(round(tv_piv_vol, 3) if tv_piv_vol is not None else "N/A"))
    lines.append("PIV50 [cc]: {0}".format(round(piv50_vol, 3) if piv50_vol is not None else "N/A"))
    lines.append("Dmin target [cGy]: {0}".format(round(dmin_cgy, 2) if dmin_cgy is not None else "N/A"))
    lines.append("Dmax target [cGy]: {0}".format(round(dmax_cgy, 2) if dmax_cgy is not None else "N/A"))

    lines.append("Índice de cobertura (TV_PIV/TV): {0}".format(round(metrics["coverage"], 4) if metrics["coverage"] is not None else "N/A"))
    lines.append("Selectividad (TV_PIV/PIV): {0}".format(round(metrics["selectivity"], 4) if metrics["selectivity"] is not None else "N/A"))
    lines.append("Índice de Paddick: {0}".format(round(metrics["paddick"], 4) if metrics["paddick"] is not None else "N/A"))
    lines.append("Índice de gradiente (PIV50/PIV100): {0}".format(round(metrics["gradient_index"], 4) if metrics["gradient_index"] is not None else "N/A"))

    lines.append("RTOG CI (PIV/TV): {0}".format(round(metrics["rtog_ci"], 4) if metrics["rtog_ci"] is not None else "N/A"))
    lines.append("Quality of Coverage (Dmin/Rx): {0}".format(round(metrics["qoc"], 4) if metrics["qoc"] is not None else "N/A"))
    lines.append("Índice de homogeneidad HI (Dmax/Rx): {0}".format(round(metrics["hi"], 4) if metrics["hi"] is not None else "N/A"))
    lines.append("New Conformity Index NCI ((TV*PIV)/TV_PIV^2): {0}".format(round(metrics["nci"], 4) if metrics["nci"] is not None else "N/A"))

    block = "\n".join(lines)
    print("\n" + block)
    return block


def main():
    case = get_current("Case")
    plan = get_current("Plan")
    beam_set = get_current("BeamSet")
    exam = get_current("Examination")

    ptv_candidates = [
        r.Name for r in case.PatientModel.RegionsOfInterest if r.Name.upper().startswith("PTV")
    ]
    if not ptv_candidates:
        raise RuntimeError("No se encontraron ROI tipo PTV (nombres que inicien con 'PTV').")

    selected_ptvs = select_ptvs(ptv_candidates)
    if not selected_ptvs:
        raise RuntimeError("No se seleccionaron PTV(s).")

    rx_cgy = get_prescription_dose_cgy(beam_set)
    half_rx_cgy = 0.5 * rx_cgy

    roi_iso_100 = "Iso_Rx_100"
    roi_iso_50 = "Iso_Rx_50"

    create_isodose_roi(case, plan, roi_iso_100, rx_cgy, color="Yellow")
    create_isodose_roi(case, plan, roi_iso_50, half_rx_cgy, color="Orange")

    total_dose = plan.TreatmentCourse.TotalDose

    piv100_vol = get_roi_volume_cc(case, exam, roi_iso_100)
    piv50_vol = get_roi_volume_cc(case, exam, roi_iso_50)

    if piv100_vol is None:
        raise RuntimeError("No se pudo obtener PIV100 (isodosis de prescripción).")
    if piv50_vol is None:
        raise RuntimeError("No se pudo obtener PIV50 (50% de prescripción).")

    report_blocks = []

    for ptv_name in selected_ptvs:
        inter_roi = "tmp_{0}_IN_Iso100".format(ptv_name)
        create_intersection_roi(case, exam, inter_roi, ptv_name, roi_iso_100)

        tv_vol = get_roi_volume_cc(case, exam, ptv_name)
        tv_piv100_vol = get_roi_volume_cc(case, exam, inter_roi)
        dmin_cgy = _get_dose_statistic(total_dose, ptv_name, "Min")
        dmax_cgy = _get_dose_statistic(total_dose, ptv_name, "Max")

        if tv_vol is None:
            warn = "[WARN] {0}: volumen inválido o sin contornos.".format(ptv_name)
            print("\n" + warn)
            report_blocks.append(warn)
            continue
        if tv_piv100_vol is None:
            warn = "[WARN] {0}: intersección con isodosis Rx no válida.".format(ptv_name)
            print("\n" + warn)
            report_blocks.append(warn)
            continue

        report_blocks.append(
            print_metrics(
                "Métricas para {0}".format(ptv_name),
                tv_vol,
                piv100_vol,
                tv_piv100_vol,
                piv50_vol,
                rx_cgy,
                dmin_cgy,
                dmax_cgy,
            )
        )

    if len(selected_ptvs) > 1:
        union_roi = "tmp_PTV_union"
        inter_union_roi = "tmp_PTV_union_IN_Iso100"

        create_union_roi(case, exam, union_roi, selected_ptvs)
        create_intersection_roi(case, exam, inter_union_roi, union_roi, roi_iso_100)

        tv_union = get_roi_volume_cc(case, exam, union_roi)
        tv_piv_union = get_roi_volume_cc(case, exam, inter_union_roi)

        if tv_union is not None and tv_piv_union is not None:
            dmin_union = _get_dose_statistic(total_dose, union_roi, "Min")
            dmax_union = _get_dose_statistic(total_dose, union_roi, "Max")
            report_blocks.append(
                print_metrics(
                    "Métricas combinadas (unión de PTVs)",
                    tv_union,
                    piv100_vol,
                    tv_piv_union,
                    piv50_vol,
                    rx_cgy,
                    dmin_union,
                    dmax_union,
                )
            )

    if report_blocks:
        show_results("\n\n".join(report_blocks))


if __name__ == "__main__":
    main()
