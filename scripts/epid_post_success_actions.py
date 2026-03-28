# -*- coding: utf-8 -*-
import os

BASE_VERIFIC_PATH = r"W:\Radiofisica\Fisica\MEDIDAS\verific_pacientes"
QA_EXPORT_PATH = r"\\srvvariadicom\QA"


def get_nhc_from_patient(patient):
    """Obtiene NHC desde PatientID (fallbacks incluidos)."""
    for attr in ("PatientID", "PatientId", "Id"):
        value = getattr(patient, attr, None)
        if value:
            return str(value).strip()
    raise RuntimeError("No se pudo obtener NHC/PatientID del paciente activo")


def ensure_patient_folder(base_folder, nhc):
    folder = os.path.join(base_folder, nhc)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def export_plan_only(case, qa_beam_set, export_folder):
    """Exporta SOLO plan (sin dosis). Adaptado con fallback para distintas versiones."""
    if not os.path.isdir(export_folder):
        os.makedirs(export_folder)

    errors = []

    # Intento 1: API habitual por BeamSetIdentifier()
    try:
        case.ScriptableDicomExport(
            ExportFolderPath=export_folder,
            BeamSets=[qa_beam_set.BeamSetIdentifier()],
            IgnorePreConditionWarnings=True,
        )
        return
    except Exception as exc:
        errors.append("Intento1: {}".format(exc))

    # Intento 2: usando DicomPlanLabel
    try:
        case.ScriptableDicomExport(
            ExportFolderPath=export_folder,
            BeamSets=[qa_beam_set.DicomPlanLabel],
            IgnorePreConditionWarnings=True,
        )
        return
    except Exception as exc:
        errors.append("Intento2: {}".format(exc))

    # Intento 3: algunas versiones requieren 'BeamSetNames'
    try:
        case.ScriptableDicomExport(
            ExportFolderPath=export_folder,
            BeamSetNames=[qa_beam_set.DicomPlanLabel],
            IgnorePreConditionWarnings=True,
        )
        return
    except Exception as exc:
        errors.append("Intento3: {}".format(exc))

    raise RuntimeError(
        "No se pudo exportar plan QA (solo plan) con ScriptableDicomExport. "
        "Detalles: {}".format(" | ".join(errors))
    )


def run_post_success(case, patient, qa_beam_set):
    nhc = get_nhc_from_patient(patient)
    patient_measure_folder = ensure_patient_folder(BASE_VERIFIC_PATH, nhc)
    export_plan_only(case, qa_beam_set, QA_EXPORT_PATH)
    return nhc, patient_measure_folder, QA_EXPORT_PATH
