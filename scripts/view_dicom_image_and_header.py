#!/usr/bin/env python3
"""Selecciona un archivo DICOM, muestra la imagen y hace print del header.

Uso:
  python scripts/view_dicom_image_and_header.py
  python scripts/view_dicom_image_and_header.py --file /ruta/archivo.dcm
"""

import argparse
import sys

import pydicom
from pydicom.pixel_data_handlers.util import apply_modality_lut


def parse_args():
    parser = argparse.ArgumentParser(
        description="Visualizar imagen DICOM e imprimir su header"
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        default=None,
        help="Ruta al archivo DICOM (si no se indica, se abre selector)",
    )
    return parser.parse_args()


def choose_file_dialog():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(
            "tkinter no está disponible. Usa --file /ruta/archivo.dcm"
        ) from exc

    root = tk.Tk()
    root.withdraw()
    root.update()

    file_path = filedialog.askopenfilename(
        title="Selecciona archivo DICOM",
        filetypes=[
            ("DICOM", "*.dcm"),
            ("Todos los archivos", "*.*"),
        ],
    )

    root.destroy()
    return file_path


def print_header(ds):
    print("\n" + "=" * 80)
    print("DICOM HEADER")
    print("=" * 80)
    print(ds)


def get_display_array(ds):
    if "PixelData" not in ds:
        return None

    arr = ds.pixel_array

    # Aplica LUT de modalidad si existe (rescale, etc.)
    try:
        arr = apply_modality_lut(arr, ds)
    except Exception:
        pass

    # Si es MONOCHROME1, invierte para visualización intuitiva
    photometric = str(getattr(ds, "PhotometricInterpretation", "")).upper()
    if photometric == "MONOCHROME1":
        arr = arr.max() - arr

    return arr


def show_image(arr, ds, file_path):
    if arr is None:
        print("\n[INFO] El DICOM no contiene PixelData. Solo se imprime header.")
        return

    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(
            "matplotlib no está disponible. Instálalo o usa entorno con GUI para ver imagen."
        ) from exc

    plt.figure(figsize=(8, 8))
    plt.imshow(arr, cmap="gray")
    plt.axis("off")

    patient = getattr(ds, "PatientName", "N/A")
    modality = getattr(ds, "Modality", "N/A")
    plt.title("{}\nPaciente: {} | Modalidad: {}".format(file_path, patient, modality))

    plt.tight_layout()
    plt.show()


def main():
    args = parse_args()

    file_path = args.file_path
    if not file_path:
        file_path = choose_file_dialog()

    if not file_path:
        print("No se seleccionó archivo.")
        return 1

    try:
        ds = pydicom.dcmread(file_path)
    except Exception as exc:
        print("[ERROR] No se pudo leer el DICOM: {}".format(exc))
        return 1

    print_header(ds)
    arr = get_display_array(ds)
    show_image(arr, ds, file_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
