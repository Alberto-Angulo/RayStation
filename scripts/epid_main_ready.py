# -*- coding: utf-8 -*-
import glob
import importlib.util
import os

import numpy as np
import pydicom

LOCAL_UTILS = r"C:\Scripts\ray_epid_qa_utils.py"
FIX_MODE = "photometric"  # "photometric" o "pixel" o "none"


def _load_local_utils(local_utils_path):
    if not os.path.exists(local_utils_path):
        raise RuntimeError("No existe ray_epid_qa_utils.py en: {}".format(local_utils_path))
    spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", local_utils_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fix_photometric(export_path):
    for fp in glob.glob(os.path.join(export_path, "*.dcm")):
        ds = pydicom.dcmread(fp)
        if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.save_as(fp)


def _invert_pixels(export_path):
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


def run_epid_from_main(
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
    epid_qa = _load_local_utils(LOCAL_UTILS)
    target = epid_qa.ray_epid_qa_utils if hasattr(epid_qa, "ray_epid_qa_utils") else epid_qa

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

    if FIX_MODE == "photometric":
        _fix_photometric(export_path)
    elif FIX_MODE == "pixel":
        _invert_pixels(export_path)
