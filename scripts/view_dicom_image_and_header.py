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
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Mostrar sin normalización (útil para depuración)",
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




def normalize_for_display(arr):
    """Normaliza una imagen para visualización evitando pantallas negras por rango."""
    import numpy as np

    a = arr.astype(np.float32)
    finite = np.isfinite(a)
    if not finite.any():
        return np.zeros_like(a, dtype=np.float32)

    vals = a[finite]

    # Percentiles robustos para evitar outliers extremos
    p1, p99 = np.percentile(vals, [1, 99])

    if p99 <= p1:
        amin, amax = vals.min(), vals.max()
        if amax <= amin:
            return np.zeros_like(a, dtype=np.float32)
        out = (a - amin) / (amax - amin)
        return np.clip(out, 0.0, 1.0)

    out = (a - p1) / (p99 - p1)
    return np.clip(out, 0.0, 1.0)




def select_image_plane(arr):
    """Convierte a plano 2D apto para imshow.

    - 2D: se devuelve directo.
    - 3D color (H,W,3|4): se devuelve directo.
    - 3D volumétrico (frames,rows,cols): se toma corte central del eje 0.
    - >3D: se reduce por ejes extra tomando índice central hasta 2D/3D-color.
    """
    import numpy as np

    a = np.asarray(arr)

    if a.ndim == 2:
        return a, "2D"

    if a.ndim == 3:
        # Imagen color estándar
        if a.shape[-1] in (3, 4):
            return a, "RGB/RGBA"

        # Volumen multiframe típico DICOM: (n_frames, rows, cols)
        mid = a.shape[0] // 2
        return a[mid, :, :], "3D->slice axis0={0}".format(mid)

    # Casos más raros (>3D): reducir progresivamente
    while a.ndim > 3:
        mid = a.shape[0] // 2
        a = a[mid]

    if a.ndim == 3 and a.shape[-1] not in (3, 4):
        mid = a.shape[0] // 2
        a = a[mid, :, :]
        return a, "ND->slice axis0={0}".format(mid)

    return a, "ND"


def show_image(arr, ds, file_path, raw=False):
    if arr is None:
        print("\n[INFO] El DICOM no contiene PixelData. Solo se imprime header.")
        return

    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(
            "matplotlib no está disponible. Instálalo o usa entorno con GUI para ver imagen."
        ) from exc

    import numpy as np

    plane, plane_info = select_image_plane(arr)

    display_arr = plane if raw else normalize_for_display(plane)

    print("\n[INFO] Shape original: {}".format(arr.shape))
    print("[INFO] Plano mostrado: {} | Shape mostrada: {}".format(plane_info, display_arr.shape))
    print("[INFO] Rango original (plano): min={:.3f}, max={:.3f}".format(float(np.min(plane)), float(np.max(plane))))
    if not raw:
        print("[INFO] Mostrando imagen normalizada por percentiles (1-99).")

    plt.figure(figsize=(8, 8))
    if raw:
        plt.imshow(display_arr, cmap="gray")
    else:
        plt.imshow(display_arr, cmap="gray", vmin=0.0, vmax=1.0)
    plt.axis("off")

    patient = getattr(ds, "PatientName", "N/A")
    modality = getattr(ds, "Modality", "N/A")
    plt.title("{}\nPaciente: {} | Modalidad: {} | {}".format(file_path, patient, modality, plane_info))

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
    show_image(arr, ds, file_path, raw=args.raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
