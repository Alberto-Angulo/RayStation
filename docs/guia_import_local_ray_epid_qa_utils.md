# Cómo usar `ray_epid_qa_utils.py` local cuando no tienes permisos en carpeta de RayStation

Si no puedes modificar scripts dentro de la carpeta protegida de RayStation, puedes cargar tu versión local de `ray_epid_qa_utils.py` desde otra ruta de disco.

## 1) Qué hace esta línea

```python
epid_qa = __import__("EPID QA.ray_epid_qa_utils")
```

- `__import__` es el mecanismo interno de Python para importar módulos dinámicamente.
- Aquí intenta importar el módulo `ray_epid_qa_utils` dentro del paquete `EPID QA`.
- El problema: nombres con espacios (`EPID QA`) y rutas fuera de `sys.path` suelen causar comportamientos frágiles.

---

## 2) Enfoque recomendado: cargar por ruta absoluta (sin tocar carpeta RayStation)

### Opción A (más robusta): `importlib.util.spec_from_file_location`

```python
import importlib.util
import os

LOCAL_UTILS = r"C:\Users\tu_usuario\raystation_local\ray_epid_qa_utils.py"

if not os.path.exists(LOCAL_UTILS):
    raise RuntimeError("No existe utils local: {}".format(LOCAL_UTILS))

spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", LOCAL_UTILS)
epid_qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epid_qa)

# Ahora puedes usar:
# epid_qa.mi_funcion(...)
```

Ventajas:
- No depende de permisos en la carpeta protegida.
- No depende de que el paquete tenga nombre válido sin espacios.
- Control total sobre qué archivo exacto cargas.

---

## 3) Opción alternativa: añadir carpeta local a `sys.path`

```python
import os
import sys

LOCAL_DIR = r"C:\Users\tu_usuario\raystation_local"
if LOCAL_DIR not in sys.path:
    sys.path.insert(0, LOCAL_DIR)

import ray_epid_qa_utils as epid_qa
```

Esto funciona bien si el archivo local se llama exactamente `ray_epid_qa_utils.py` y la carpeta es accesible.

---

## 4) Patrón de fallback recomendado (local primero, RayStation después)

```python
import importlib.util
import os

LOCAL_UTILS = r"C:\Users\tu_usuario\raystation_local\ray_epid_qa_utils.py"

if os.path.exists(LOCAL_UTILS):
    spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", LOCAL_UTILS)
    epid_qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(epid_qa)
else:
    # fallback al import original del entorno RayStation
    epid_qa = __import__("EPID QA.ray_epid_qa_utils")
```

---

## 5) Recomendaciones prácticas en hospital

1. Guarda tus scripts locales en una carpeta de usuario (p.ej. `C:\Users\<usuario>\raystation_local`).
2. Evita espacios en nombres de paquete/módulo propios.
3. Registra con `print(__file__)` o logs qué versión de `utils` se cargó.
4. Si TI bloquea algunas rutas, usa una permitida por política y documentada.

---

## 6) Resumen rápido

Sí, tu intuición es correcta: la línea con `__import__` está cargando dinámicamente el módulo.
Para tu caso (sin permisos en carpeta RayStation), la solución más segura es **cargar `ray_epid_qa_utils.py` por ruta absoluta con `importlib`**.
