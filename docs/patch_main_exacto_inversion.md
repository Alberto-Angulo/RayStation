# Patch exacto para tu `main` (sin tocar `ray_epid_qa_utils.py`)

Este patch está pensado para el código que pegaste.

## 1) Sustituye tu import de utils

Cambia esto:

```python
epid_qa = __import__("C:/Scripts/ray_epid_qa_utils")
```

por esto:

```python
import importlib.util
import glob
import pydicom
import numpy as np

LOCAL_UTILS = r"C:\Scripts\ray_epid_qa_utils.py"  # <-- CAMBIA SOLO ESTA RUTA

spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", LOCAL_UTILS)
epid_qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epid_qa)
```

## 2) Añade esta función en el `main` (por ejemplo encima de `class MyWindow`)

```python
def invert_exported_dicoms(export_path):
    dcm_files = glob.glob(os.path.join(export_path, "*.dcm"))
    for fp in dcm_files:
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
```

## 3) En `RunClicked`, justo después de `compute_epid_qa_response(...)`, añade:

```python
invert_exported_dicoms(export_path)
```

Quedaría así:

```python
epid_qa.compute_epid_qa_response(
    patient, plan, self.beam_set, grid_resolution, phantom_name, phantom_id,
    collimator_angle, sid, isocenter, detector_plane_y, machine_sad, ui,
    export_path, flood_field_method[selected_flood_field_method_index],
    flood_field_beam_quality_id[selected_flood_field_method_index]
)

invert_exported_dicoms(export_path)
```

## 4) Nota importante por compatibilidad

En tu snippet usabas:

```python
epid_qa.ray_epid_qa_utils.compute_epid_qa_response(...)
```

Con `importlib` por ruta local, normalmente la llamada correcta será:

```python
epid_qa.compute_epid_qa_response(...)
```

---

## 5) Si quieres una versión menos agresiva

Si prefieres no tocar `PixelData`, prueba solo con metadata:

```python
def fix_only_photometric(export_path):
    dcm_files = glob.glob(os.path.join(export_path, "*.dcm"))
    for fp in dcm_files:
        ds = pydicom.dcmread(fp)
        if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.save_as(fp)
```

Y llamas `fix_only_photometric(export_path)` tras el compute.
