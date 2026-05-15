# Invertir grises sin tocar `ray_epid_qa_utils.py` (solo modificando `ray_epid_qa_main.py`)

Sí, **se puede**.
Si no puedes modificar `utils`, tienes dos estrategias desde `main`:

1. **Corregir solo metadata DICOM** (`PhotometricInterpretation`) tras exportar.
2. **Invertir píxel a píxel** en los DICOM ya exportados (post-procesado).

---

## 1) Opción recomendada primero: cambiar `PhotometricInterpretation`

Si el problema es únicamente visual (blanco/negro invertido), normalmente basta con:

- `MONOCHROME1` -> `MONOCHROME2` (o viceversa)

sin tocar `PixelData`.

### Código ejemplo (en `main` después de exportar)

```python
import glob
import os
import pydicom


def fix_photometric_in_export_folder(export_path):
    dcm_files = glob.glob(os.path.join(export_path, "*.dcm"))
    for fp in dcm_files:
        ds = pydicom.dcmread(fp)
        pi = str(getattr(ds, "PhotometricInterpretation", "")).upper()

        if pi == "MONOCHROME1":
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.save_as(fp)
        elif pi == "MONOCHROME2":
            # si en tu caso el visor espera lo contrario, puedes activar esto
            # ds.PhotometricInterpretation = "MONOCHROME1"
            # ds.save_as(fp)
            pass
```

---

## 2) Si no alcanza: invertir `PixelData` desde `main`

Si cambiar `PhotometricInterpretation` no arregla, entonces invierte los valores del array:

```python
import glob
import os
import numpy as np
import pydicom


def invert_pixels_in_export_folder(export_path):
    dcm_files = glob.glob(os.path.join(export_path, "*.dcm"))
    for fp in dcm_files:
        ds = pydicom.dcmread(fp)

        if "PixelData" not in ds:
            continue

        arr = ds.pixel_array.astype(np.float32)
        inv = arr.max() - arr

        # conservar rango y tipo de salida típico de imagen
        inv = np.clip(inv, 0, 65535).astype(np.uint16)

        ds.PixelData = inv.tobytes()
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = "MONOCHROME2"

        ds.save_as(fp)
```

---

## 3) Dónde llamarlo en tu flujo actual

En tu `RunClicked`, justo después de:

```python
epid_qa.ray_epid_qa_utils.compute_epid_qa_response(...)
```

añade:

```python
fix_photometric_in_export_folder(export_path)
# o, si no funciona en tu entorno:
# invert_pixels_in_export_folder(export_path)
```

---

## 4) Validación rápida

1. Exporta un caso de prueba.
2. Abre DICOM en RayStation y en un visor externo.
3. Verifica que alta señal/dosis se vea con contraste esperado.
4. Si hay discrepancia entre visores, prioriza:
   - `PhotometricInterpretation`
   - `RescaleSlope/Intercept`
   - `WindowCenter/WindowWidth`

---

## 5) Recomendación práctica en tu caso

Como no puedes tocar `utils`, empieza por **post-procesado en `main`** con cambio de `PhotometricInterpretation`.
Es el ajuste menos invasivo.
Si no basta, pasa a inversión de `PixelData` también desde `main`.
