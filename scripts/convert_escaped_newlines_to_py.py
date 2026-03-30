#!/usr/bin/env python3
"""Convierte texto Python con '\n' literales a saltos reales de línea.

Uso:
  python scripts/convert_escaped_newlines_to_py.py --in origen.txt --out main_limpio.py
"""

import argparse


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="Archivo con texto escapado")
    p.add_argument("--out", dest="out_path", required=True, help="Archivo .py de salida")
    return p.parse_args()


def main():
    args = parse_args()
    with open(args.in_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Convierte solo saltos/carriage explícitos para evitar romper rutas Windows con \U...
    fixed = raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")

    with open(args.out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fixed)

    print("OK ->", args.out_path)


if __name__ == "__main__":
    main()
