# Error `get_current is not defined` en scripts de RayStation: por qué pasa y cómo arreglarlo

## Resumen corto
`get_current(...)` **solo existe dentro del entorno de scripting de RayStation** (módulo `connect`).
Si ejecutas el script en PyCharm/Python normal sin ese entorno, `get_current` no estará disponible.

---

## 1) Causa más común

Tu script depende de:

```python
from connect import get_current
```

Si `connect` no está cargado correctamente, luego al llamar:

```python
patient = get_current('Patient')
```

obtendrás errores como `NameError: get_current is not defined`.

---

## 2) Qué revisar paso a paso

1. **No uses `from connect import *`**: usa import explícito.
2. Verifica que el script se lanza desde RayStation ScriptClient (o entorno con `connect` disponible).
3. Si corres desde PyCharm, valida que el intérprete y `PYTHONPATH` apuntan al runtime de RayStation (si tu hospital lo permite).
4. Añade un chequeo temprano para fallar con mensaje claro.

---

## 3) Patrón recomendado (robusto)

```python
try:
    from connect import get_current
except Exception as exc:
    raise RuntimeError(
        "No se pudo importar 'connect.get_current'. "
        "Este script debe ejecutarse dentro de RayStation ScriptClient."
    ) from exc

# Validación explícita
if 'get_current' not in globals() or get_current is None:
    raise RuntimeError("get_current no está disponible en este entorno.")

machine_db = get_current('MachineDB')
ui = get_current('ui')
patient = get_current('Patient')
beam_set = get_current('BeamSet')
plan = get_current('Plan')
```

---

## 4) Integración con tu bloque actual

En tu código actual tienes:

```python
from connect import *
```

Cámbialo por:

```python
from connect import get_current
```

Y añade el bloque `try/except` de arriba.

---

## 5) Nota importante sobre el import local de `utils`

Tu carga local con `importlib` está bien para `ray_epid_qa_utils.py`.
Pero eso **no sustituye** al módulo `connect` de RayStation.

Es decir:
- `ray_epid_qa_utils.py` local ✅
- `get_current(...)` requiere entorno RayStation ✅

---

## 6) Recomendación práctica

Si quieres depurar en local (PyCharm):
- separa lógica pura (funciones matemáticas/IO) en módulos independientes,
- y deja una capa mínima “RayStation-only” para llamadas a `get_current`.

Así puedes testear casi todo fuera de RayStation y solo conectar objetos clínicos dentro de RayStation.
