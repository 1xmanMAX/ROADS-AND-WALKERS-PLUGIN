"""Punto de entrada de Corredor Simple.

  python CorredorSimple.py                       -> abre la ventana
  python CorredorSimple.py <carpeta_proyecto>    -> abre la ventana con ese proyecto
  python CorredorSimple.py calcular <carpeta_proyecto> <carpeta_salida> [BM lectura_atras]
                                                 -> calcula y exporta sin ventana
"""
import sys


def consola(args):
    from corredor.datos import leer_proyecto, validar_proyecto
    from corredor.exportar import altura_instrumento, exportar_todo
    from corredor.motor import calcular

    proy = leer_proyecto(args[0])
    err = validar_proyecto(proy)
    if err:
        print("\n".join(err))
        return 1
    res = calcular(proy)
    ai = altura_instrumento(proy, args[2], float(args[3])) if len(args) >= 4 else None
    for a in res.avisos:
        print(a.texto())
    for k, rc in res.calles.items():
        print(f"{k}: corte {rc.vol_corte:.2f} m3, relleno {rc.vol_relleno:.2f} m3, neto {rc.vol_neto:.2f} m3")
    for f in exportar_todo(res, args[1], ai):
        print("  ->", f)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "calcular":
        sys.exit(consola(sys.argv[2:]))
    from corredor.app import main
    main()
