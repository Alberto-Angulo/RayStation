# RayStation EPID virtual DICOM: por qué se invierte la dosis y cómo arreglarlo

Esta guía explica el problema típico: al exportar un DICOM de imagen EPID virtual, visualmente parece que los niveles de dosis están invertidos (zonas altas se ven oscuras y bajas claras, o al revés).

## 1) Qué suele estar pasando (causas más frecuentes)

### Causa A: Photometric Interpretation (`0028,0004`)
En DICOM de imagen en escala de grises, el tag **PhotometricInterpretation** define cómo interpretar el pixel:

- `MONOCHROME1`: mayor valor de pixel = más negro.
- `MONOCHROME2`: mayor valor de pixel = más blanco.

Si tu pipeline crea una imagen con lógica de `MONOCHROME2` pero escribe `MONOCHROME1` (o al revés), el visor la mostrará invertida.

### Causa B: `RescaleSlope` / `RescaleIntercept`
Si exportas con reescalado físico (por ejemplo dosis relativa o señal), una combinación errónea de slope/intercept puede invertir o desplazar el rango.

### Causa C: tipo de dato y signo (`PixelRepresentation`)
- `PixelRepresentation = 0` => unsigned
- `PixelRepresentation = 1` => signed

Si la matriz real no coincide con lo que declara el header, algunos visores recalculan mal niveles.

### Causa D: LUT/VOI/window en el visor
A veces el DICOM está correcto, pero el visor aplica Window/Level o LUT invertida por presets.

---

## 2) Diagnóstico paso a paso

1. **Inspecciona metadata clave** del DICOM exportado:
   - `PhotometricInterpretation`
   - `BitsAllocated`, `BitsStored`, `HighBit`
   - `PixelRepresentation`
   - `RescaleSlope`, `RescaleIntercept`
   - `WindowCenter`, `WindowWidth`
2. **Compara min/max** de tu matriz original vs `pixel_array` leído del DICOM exportado.
3. **Valida correlación física**:
   - Si en la matriz original “más dosis = mayor valor”, tras exportar/leer debería mantenerse.
4. **Prueba en dos visores** (p.ej. RayStation y un visor externo) para separar problema de archivo vs visualización.

---

## 3) Corrección recomendada (práctica)

### Regla práctica
Si tu matriz cumple **más dosis = mayor valor numérico**, usa:
- `PhotometricInterpretation = "MONOCHROME2"`

Y evita invertir manualmente (`max - img`) a menos que tu flujo realmente lo necesite.

### Checklist de exportación segura
- Convertir a `uint16` antes de escribir `PixelData`.
- Setear:
  - `BitsAllocated = 16`
  - `BitsStored = 16`
  - `HighBit = 15`
  - `PixelRepresentation = 0`
- Alinear `Rows/Columns` con la matriz real.
- Definir `RescaleSlope = 1`, `RescaleIntercept = 0` si no requieres reescalado físico.

---

## 4) Función de validación recomendada

Puedes añadir una validación tras exportar para detectar inversión automáticamente.

```python
import pydicom
import numpy as np


def validate_epid_export(path, source_array):
    ds = pydicom.dcmread(path)
    px = ds.pixel_array.astype(np.float32)

    print("PhotometricInterpretation:", getattr(ds, "PhotometricInterpretation", None))
    print("PixelRepresentation:", getattr(ds, "PixelRepresentation", None))
    print("RescaleSlope:", getattr(ds, "RescaleSlope", None))
    print("RescaleIntercept:", getattr(ds, "RescaleIntercept", None))

    src = source_array.astype(np.float32)

    # Correlación directa e invertida
    corr_direct = np.corrcoef(src.ravel(), px.ravel())[0, 1]
    corr_invert = np.corrcoef(src.ravel(), (-px).ravel())[0, 1]

    print("corr_direct:", corr_direct)
    print("corr_invert:", corr_invert)

    if corr_invert > corr_direct:
        print("[WARN] Posible inversión de niveles detectada")
    else:
        print("[OK] Orden de niveles consistente")
```

---

## 5) Patrón típico de fix en utilidades de exportación

En tu `ray_epid_qa_utils.py`, revisa especialmente estas líneas/patrones:

1. Cualquier inversión explícita de matriz:
   - `img = img.max() - img`
   - `img = np.flipud(img)` / `np.fliplr(img)` (esto invierte orientación espacial, no niveles, pero puede confundir diagnóstico)
2. `PhotometricInterpretation` final escrito en el dataset.
3. Conversión de dtype antes de `PixelData`.
4. Slope/intercept no intencionados.

Si deseas, en cuanto compartas `ray_epid_qa_main.py` y `ray_epid_qa_utils.py` en este repo, te marco línea por línea exactamente dónde se está invirtiendo y te propongo patch directo.
