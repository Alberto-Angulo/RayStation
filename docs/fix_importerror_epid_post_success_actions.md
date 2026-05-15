# Fix rápido: `ImportError: No module named 'epid_post_success_actions'`

Ese error aparece porque RayStation no está encontrando el módulo en `sys.path`.

## Solución más simple (recomendada)

No uses import externo. Copia/pega el bloque de:

- `scripts/epid_post_success_embedded.py`

directamente dentro de tu `main` (encima de `class MyWindow`).

Así eliminas por completo la dependencia `from epid_post_success_actions import run_post_success`.

## Si prefieres mantener archivo externo

Carga por ruta absoluta:

```python
import importlib.util

POST_SUCCESS_PATH = r"C:\ruta\a\epid_post_success_actions.py"
spec = importlib.util.spec_from_file_location("epid_post_success_actions", POST_SUCCESS_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
run_post_success = mod.run_post_success
```

Con esto también evitas depender de `sys.path`.
