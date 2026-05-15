# Cómo convertir un script pegado con `\n` a un `.py` válido

Si te pasan el script con `\n` literales (todo en una línea), usa:

```bash
python scripts/convert_escaped_newlines_to_py.py --in main_pegado.txt --out main_limpio.py
```

## Pasos
1. Copia el texto largo (con `\n`) en `main_pegado.txt`.
2. Ejecuta el comando anterior.
3. Abre `main_limpio.py` y ejecútalo en RayStation.

El conversor solo transforma `\n`/`\r` literales para evitar romper rutas Windows.
