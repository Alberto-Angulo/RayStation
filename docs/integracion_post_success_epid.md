# Integración en tu `main`: carpeta NHC + export DICOM plan QA

Este bloque añade dos acciones al terminar exitosamente `RunClicked`:

1. Crear carpeta del paciente (NHC) en `W:\Radiofisica\Fisica\MEDIDAS\verific_pacientes\<NHC>`.
2. Exportar el plan QA (solo plan, sin dosis) a `\\srvvariadicom\QA`.

## 1) Import en tu main

```python
from epid_post_success_actions import run_post_success
```

## 2) En `RunClicked`, justo después de `compute_epid_qa_response(...)` y de `invert_exported_dicoms(export_path)`

```python
# qa_beam_set: usa el beam set de QA creado. Si tu flujo devuelve otro objeto, cámbialo aquí.
qa_beam_set = self.beam_set

nhc, nhc_folder, qa_export_folder = run_post_success(
    case=get_current('Case'),
    patient=patient,
    qa_beam_set=qa_beam_set,
)

# Si quieres, redirige export_path de imágenes al folder NHC:
# export_path = nhc_folder

print("NHC:", nhc)
print("Carpeta paciente:", nhc_folder)
print("Plan QA exportado en:", qa_export_folder)
```

> Nota: la API de RayStation para identificar exactamente el beam set QA puede variar según versión/flujo.
> Si en tu script tienes una variable específica para el QA beam set, úsala en `qa_beam_set`.
