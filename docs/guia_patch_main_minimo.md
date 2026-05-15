# Patch mínimo listo para copiar/pegar en `ray_epid_qa_main.py`

Archivo listo:
- `scripts/ray_epid_qa_main_patch_min.py`

## Qué tienes que cambiar tú (solo 2 cosas)

1. Ruta local de utils:

```python
local_utils = r"C:\Users\TU_USUARIO\raystation_local\ray_epid_qa_utils.py"
```

2. Modo de corrección:

```python
fix_mode="photometric"   # recomendado primero
# o
fix_mode="pixel"         # si photometric no alcanza
```

## Cómo integrarlo en tu `RunClicked`

Reemplaza esta llamada:

```python
epid_qa.ray_epid_qa_utils.compute_epid_qa_response(...)
```

por:

```python
run_epid_export(
    patient=patient,
    plan=plan,
    beam_set=self.beam_set,
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
    flood_field_method=flood_field_method[selected_flood_field_method_index],
    flood_field_beam_quality_id=flood_field_beam_quality_id[selected_flood_field_method_index],
)
```

Con eso no necesitas modificar `ray_epid_qa_utils.py`.
