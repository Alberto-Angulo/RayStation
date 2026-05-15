# Reemplazo directo en tu `main` (copiar/pegar)

## Bloque A: reemplaza la línea de import de utils

Reemplaza:

```python
epid_qa = __import__("EPID QA.ray_epid_qa_utils")
```

por:

```python
import glob
import importlib.util
import numpy as np
import pydicom

LOCAL_UTILS = r"C:\Scripts\ray_epid_qa_utils.py"

spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", LOCAL_UTILS)
epid_qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epid_qa)


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

## Bloque B: reemplaza SOLO la llamada de compute dentro de `RunClicked`

Reemplaza esto:

```python
epid_qa.ray_epid_qa_utils.compute_epid_qa_response(patient, plan, self.beam_set, grid_resolution, phantom_name, phantom_id,
                         collimator_angle, sid, isocenter, detector_plane_y, machine_sad, ui,
                         export_path, flood_field_method[selected_flood_field_method_index],
                         flood_field_beam_quality_id[selected_flood_field_method_index])
```

por esto:

```python
target = epid_qa.ray_epid_qa_utils if hasattr(epid_qa, "ray_epid_qa_utils") else epid_qa

target.compute_epid_qa_response(
    patient, plan, self.beam_set, grid_resolution, phantom_name, phantom_id,
    collimator_angle, sid, isocenter, detector_plane_y, machine_sad, ui,
    export_path, flood_field_method[selected_flood_field_method_index],
    flood_field_beam_quality_id[selected_flood_field_method_index]
)

invert_exported_dicoms(export_path)
```

Con esos dos cambios, mantienes todo tu `main` intacto (UI/XAML/etc.) y solo añades la inversión de niveles tras exportar.
