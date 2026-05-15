# -*- coding: utf-8 -*-
import glob
import importlib.util
import os


def load_epid_utils(local_utils_path, fallback_import_path="EPID QA.ray_epid_qa_utils"):
    if os.path.exists(local_utils_path):
        spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", local_utils_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return __import__(fallback_import_path, fromlist=["*"])


def fix_photometric_in_export_folder(export_path):
    import pydicom

    for fp in glob.glob(os.path.join(export_path, "*.dcm")):
        ds = pydicom.dcmread(fp)
        pi = str(getattr(ds, "PhotometricInterpretation", "")).upper()
        if pi == "MONOCHROME1":
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.save_as(fp)


def invert_pixels_in_export_folder(export_path):
    import numpy as np
    import pydicom

    for fp in glob.glob(os.path.join(export_path, "*.dcm")):
        ds = pydicom.dcmread(fp)
        if "PixelData" not in ds:
            continue
        arr = ds.pixel_array.astype(np.float32)
        inv = arr.max() - arr
        inv = np.clip(inv, 0, 65535).astype(np.uint16)
        ds.PixelData = inv.tobytes()
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.save_as(fp)


def compute_and_fix_epid_export(
    epid_qa_module,
    patient,
    plan,
    beam_set,
    grid_resolution,
    phantom_name,
    phantom_id,
    collimator_angle,
    sid,
    isocenter,
    detector_plane_y,
    machine_sad,
    ui,
    export_path,
    flood_field_method,
    flood_field_beam_quality_id,
    fix_mode="photometric",
):
    target = epid_qa_module.ray_epid_qa_utils if hasattr(epid_qa_module, "ray_epid_qa_utils") else epid_qa_module
    target.compute_epid_qa_response(
        patient,
        plan,
        beam_set,
        grid_resolution,
        phantom_name,
        phantom_id,
        collimator_angle,
        sid,
        isocenter,
        detector_plane_y,
        machine_sad,
        ui,
        export_path,
        flood_field_method,
        flood_field_beam_quality_id,
    )
    if fix_mode == "photometric":
        fix_photometric_in_export_folder(export_path)
    elif fix_mode == "pixel":
        invert_pixels_in_export_folder(export_path)


def run_epid_export(
    patient,
    plan,
    beam_set,
    grid_resolution,
    phantom_name,
    phantom_id,
    collimator_angle,
    sid,
    isocenter,
    detector_plane_y,
    machine_sad,
    ui,
    export_path,
    flood_field_method,
    flood_field_beam_quality_id,
):
    local_utils = r"C:\Users\TU_USUARIO\raystation_local\ray_epid_qa_utils.py"
    epid_qa = load_epid_utils(local_utils)
    compute_and_fix_epid_export(
        epid_qa_module=epid_qa,
        patient=patient,
        plan=plan,
        beam_set=beam_set,
        grid_resolution=grid_resolution,
        phantom_name=phantom_name,
        phantom_id=phantom_id,
        collimator_angle=collimator_angle,
        sid=sid,
        isocenter=isocenter,
        detector_plane_y=detector_plane_y,
        machine_sad=machine_sad,
        ui=ui,
        export_path=export_path,
        flood_field_method=flood_field_method,
        flood_field_beam_quality_id=flood_field_beam_quality_id,
        fix_mode="photometric",
    )
