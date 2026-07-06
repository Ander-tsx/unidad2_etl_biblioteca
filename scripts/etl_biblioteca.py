import os
import sys
import json
import datetime
from pathlib import Path

import pandas as pd
import mysql.connector
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE    = PROJECT_ROOT / "data" / "prestamos_biblioteca_100.csv"
EVIDENCIAS   = PROJECT_ROOT / "evidencias"
REPORTE_TXT  = EVIDENCIAS / "reporte_ejecucion.txt"

load_dotenv(PROJECT_ROOT / ".env")

DB_HOST          = os.getenv("DB_HOST", "localhost")
DB_PORT          = int(os.getenv("DB_PORT", 3307))
DB_USER          = os.getenv("DB_USER", "root")
DB_PASSWORD      = os.getenv("DB_PASSWORD", "")
DB_NAME          = os.getenv("DB_NAME", "biblioteca_dw")
NOMBRE_ALUMNO    = os.getenv("NOMBRE_ALUMNO", "Alumno")
GRUPO            = os.getenv("GRUPO", "")


def leer_y_limpiar_csv(ruta: Path) -> pd.DataFrame:
    """Lee el CSV, estandariza columnas y aplica limpieza básica de tipos."""
    print(f"[INFO] Leyendo archivo: {ruta}")

    df = pd.read_csv(ruta, dtype=str)

    # 1. Estandarizar nombres de columna (lower + strip)
    df.columns = [c.strip().lower() for c in df.columns]

    # 2. Strip de espacios en columnas de texto
    texto_cols = ["alumno", "carrera", "libro", "categoria", "sede"]
    for col in texto_cols:
        if col in df.columns:
            df[col] = df[col].str.strip()

    # 3. Convertir fecha_prestamo a date
    df["fecha_prestamo"] = pd.to_datetime(df["fecha_prestamo"].str.strip(),
                                          format="%Y-%m-%d", errors="coerce").dt.date

    # 4. Convertir columnas numéricas
    for col in ["dias_prestamo", "multa_diaria", "total_multa"]:
        df[col] = pd.to_numeric(df[col].str.strip(), errors="coerce")

    # 5. Verificar nulos en columnas obligatorias
    obligatorias = ["id_prestamo", "fecha_prestamo", "alumno", "carrera",
                    "libro", "categoria", "dias_prestamo", "multa_diaria",
                    "sede", "total_multa"]
    nulos = df[obligatorias].isnull().sum()
    if nulos.any():
        print("[WARN] Valores nulos detectados en columnas obligatorias:")
        print(nulos[nulos > 0])

    df["fila_csv"] = df.index + 2

    print(f"[INFO] Filas leídas del CSV: {len(df)}")
    return df

def validar(df: pd.DataFrame):
    """
    Aplica validaciones en orden y separa registros válidos de errores.
    Retorna: (df_validos, lista_errores)

    Validaciones:
      V1 - id_prestamo duplicado  → se conserva primera aparición
      V2 - total_multa incorrecto → total_multa ≠ dias_prestamo * multa_diaria
    """
    errores = []

    mask_dup = df.duplicated(subset="id_prestamo", keep="first")
    df_dup   = df[mask_dup].copy()

    for _, row in df_dup.iterrows():
        errores.append({
            "fila_csv"         : int(row["fila_csv"]),
            "id_registro"      : str(row["id_prestamo"]),
            "descripcion_error": "id_prestamo duplicado; se conserva la primera aparición",
            "datos_originales" : row.drop("fila_csv").to_dict(),
        })

    df_sin_dup = df[~mask_dup].copy()

    total_esperado = df_sin_dup["dias_prestamo"] * df_sin_dup["multa_diaria"]
    mask_multa     = df_sin_dup["total_multa"] != total_esperado

    df_multa_mal = df_sin_dup[mask_multa].copy()

    for _, row in df_multa_mal.iterrows():
        esperado = row["dias_prestamo"] * row["multa_diaria"]
        errores.append({
            "fila_csv"         : int(row["fila_csv"]),
            "id_registro"      : str(row["id_prestamo"]),
            "descripcion_error": (
                f"total_multa incorrecto: valor={row['total_multa']}, "
                f"esperado={esperado} ({row['dias_prestamo']}×{row['multa_diaria']})"
            ),
            "datos_originales" : row.drop("fila_csv").to_dict(),
        })

    df_validos = df_sin_dup[~mask_multa].copy()

    print(f"[INFO] Registros válidos : {len(df_validos)}")
    print(f"[INFO] Registros con error: {len(errores)}")
    return df_validos, errores

def construir_dimensiones(df: pd.DataFrame):
    """
    Genera diccionarios {valor: id_secuencial} para cada dimensión a partir
    del DataFrame validado. Los IDs empiezan en 1 y son explícitos.

    Retorna un dict con claves:
      alumno_map, carrera_map, libro_map, sede_map, fecha_map
    """

    alumno_map = {v: i for i, v in enumerate(sorted(df["alumno"].unique()), start=1)}

    carrera_map = {v: i for i, v in enumerate(sorted(df["carrera"].unique()), start=1)}

    libros_unicos = sorted(df[["libro", "categoria"]].drop_duplicates()
                             .itertuples(index=False, name=None))
    libro_map = {(lib, cat): i for i, (lib, cat) in enumerate(libros_unicos, start=1)}

    sede_map = {v: i for i, v in enumerate(sorted(df["sede"].unique()), start=1)}

    fechas_unicas = sorted(df["fecha_prestamo"].unique())
    fecha_map = {f: i for i, f in enumerate(fechas_unicas, start=1)}

    return {
        "alumno_map" : alumno_map,
        "carrera_map": carrera_map,
        "libro_map"  : libro_map,
        "sede_map"   : sede_map,
        "fecha_map"  : fecha_map,
    }


DDL_STATEMENTS = """
CREATE TABLE IF NOT EXISTS dim_alumno (
    id_alumno INT PRIMARY KEY,
    alumno    VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_carrera (
    id_carrera INT PRIMARY KEY,
    carrera    VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_libro (
    id_libro   INT PRIMARY KEY,
    libro      VARCHAR(200) NOT NULL,
    categoria  VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_sede (
    id_sede INT PRIMARY KEY,
    sede    VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_fecha (
    id_fecha INT PRIMARY KEY,
    fecha    DATE NOT NULL,
    anio     INT  NOT NULL,
    mes      INT  NOT NULL,
    dia      INT  NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_prestamos (
    id_prestamo   INT PRIMARY KEY,
    id_fecha      INT NOT NULL,
    id_alumno     INT NOT NULL,
    id_carrera    INT NOT NULL,
    id_libro      INT NOT NULL,
    id_sede       INT NOT NULL,
    dias_prestamo INT NOT NULL,
    multa_diaria  DECIMAL(10,2) NOT NULL,
    total_multa   DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (id_fecha)   REFERENCES dim_fecha(id_fecha),
    FOREIGN KEY (id_alumno)  REFERENCES dim_alumno(id_alumno),
    FOREIGN KEY (id_carrera) REFERENCES dim_carrera(id_carrera),
    FOREIGN KEY (id_libro)   REFERENCES dim_libro(id_libro),
    FOREIGN KEY (id_sede)    REFERENCES dim_sede(id_sede)
);

CREATE TABLE IF NOT EXISTS etl_errores (
    id_error          INT AUTO_INCREMENT PRIMARY KEY,
    fecha_error       DATETIME      NOT NULL,
    archivo_origen    VARCHAR(255)  NOT NULL,
    fila_csv          INT           NOT NULL,
    id_registro       VARCHAR(50)   NOT NULL,
    descripcion_error VARCHAR(500)  NOT NULL,
    datos_originales  TEXT          NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_log (
    id_log           INT AUTO_INCREMENT PRIMARY KEY,
    fecha_ejecucion  DATETIME     NOT NULL,
    archivo_origen   VARCHAR(255) NOT NULL,
    filas_leidas     INT          NOT NULL,
    filas_cargadas   INT          NOT NULL,
    filas_rechazadas INT          NOT NULL,
    estado           VARCHAR(50)  NOT NULL
);
"""


def crear_tablas(cursor):
    """Ejecuta los DDL para crear tablas si no existen."""
    for stmt in DDL_STATEMENTS.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cursor.execute(stmt)
    print("[INFO] Tablas verificadas / creadas correctamente.")


def truncar_tablas(cursor):
    """
    Limpia las tablas de datos antes de cada carga (idempotencia).
    etl_log NO se trunca para conservar el historial.
    """

    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for tabla in ["fact_prestamos", "dim_alumno", "dim_carrera",
                  "dim_libro", "dim_sede", "dim_fecha", "etl_errores"]:
        cursor.execute(f"TRUNCATE TABLE {tabla}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("[INFO] Tablas truncadas (excepto etl_log).")


def cargar_dimensiones(cursor, dimaps: dict):
    """Inserta filas en todas las tablas de dimensión con IDs explícitos."""

    rows_alumno = [(id_, nombre) for nombre, id_ in dimaps["alumno_map"].items()]
    cursor.executemany(
        "INSERT INTO dim_alumno (id_alumno, alumno) VALUES (%s, %s)",
        rows_alumno
    )

    rows_carrera = [(id_, carrera) for carrera, id_ in dimaps["carrera_map"].items()]
    cursor.executemany(
        "INSERT INTO dim_carrera (id_carrera, carrera) VALUES (%s, %s)",
        rows_carrera
    )

    rows_libro = [(id_, lib, cat) for (lib, cat), id_ in dimaps["libro_map"].items()]
    cursor.executemany(
        "INSERT INTO dim_libro (id_libro, libro, categoria) VALUES (%s, %s, %s)",
        rows_libro
    )

    rows_sede = [(id_, sede) for sede, id_ in dimaps["sede_map"].items()]
    cursor.executemany(
        "INSERT INTO dim_sede (id_sede, sede) VALUES (%s, %s)",
        rows_sede
    )

    rows_fecha = [
        (id_, fecha.isoformat(), fecha.year, fecha.month, fecha.day)
        for fecha, id_ in dimaps["fecha_map"].items()
    ]
    cursor.executemany(
        "INSERT INTO dim_fecha (id_fecha, fecha, anio, mes, dia) VALUES (%s, %s, %s, %s, %s)",
        rows_fecha
    )

    print("[INFO] Dimensiones cargadas.")


def cargar_fact(cursor, df: pd.DataFrame, dimaps: dict):
    """Construye y carga fact_prestamos usando el mapeo de dimensiones."""

    rows = []
    for _, row in df.iterrows():
        rows.append((
            int(row["id_prestamo"]),
            dimaps["fecha_map"][row["fecha_prestamo"]],
            dimaps["alumno_map"][row["alumno"]],
            dimaps["carrera_map"][row["carrera"]],
            dimaps["libro_map"][(row["libro"], row["categoria"])],
            dimaps["sede_map"][row["sede"]],
            int(row["dias_prestamo"]),
            float(row["multa_diaria"]),
            float(row["total_multa"]),
        ))

    cursor.executemany(
        """INSERT INTO fact_prestamos
           (id_prestamo, id_fecha, id_alumno, id_carrera, id_libro, id_sede,
            dias_prestamo, multa_diaria, total_multa)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows
    )
    print(f"[INFO] fact_prestamos cargada: {len(rows)} registros.")


def cargar_errores(cursor, errores: list, archivo: str, fecha_error: datetime.datetime):
    """Inserta los registros rechazados en etl_errores."""
    rows = []
    for e in errores:
        datos_json = json.dumps(e["datos_originales"], default=str, ensure_ascii=False)
        rows.append((
            fecha_error,
            archivo,
            e["fila_csv"],
            e["id_registro"],
            e["descripcion_error"],
            datos_json,
        ))

    cursor.executemany(
        """INSERT INTO etl_errores
           (fecha_error, archivo_origen, fila_csv, id_registro,
            descripcion_error, datos_originales)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows
    )
    print(f"[INFO] etl_errores cargada: {len(rows)} registros.")


def cargar_log(cursor, archivo: str, fecha: datetime.datetime,
               leidas: int, cargadas: int, rechazadas: int, estado: str):
    """Inserta el resumen de la ejecución en etl_log."""
    cursor.execute(
        """INSERT INTO etl_log
           (fecha_ejecucion, archivo_origen, filas_leidas,
            filas_cargadas, filas_rechazadas, estado)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (fecha, archivo, leidas, cargadas, rechazadas, estado)
    )
    print("[INFO] etl_log actualizado.")

def generar_reporte(fecha: datetime.datetime, archivo: str,
                    leidas: int, cargadas: int, rechazadas: int,
                    estado: str, errores: list):
    """Genera evidencias/reporte_ejecucion.txt con el resumen de la ejecución."""
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)

    lineas = [
        "=" * 60,
        "   REPORTE DE EJECUCIÓN — ETL BIBLIOTECA",
        "=" * 60,
        f"Nombre del alumno    : {NOMBRE_ALUMNO}",
        f"Grupo                : {GRUPO}",
        f"Fecha y hora         : {fecha.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Archivo procesado    : {archivo}",
        "-" * 60,
        f"Filas leídas         : {leidas}",
        f"Filas cargadas       : {cargadas}",
        f"Filas rechazadas     : {rechazadas}",
        f"Estado final         : {estado}",
        "-" * 60,
        "Errores detectados:",
    ]

    if errores:
        for e in errores:
            lineas.append(
                f"  • Fila CSV {e['fila_csv']} | id_prestamo={e['id_registro']} "
                f"| {e['descripcion_error']}"
            )
    else:
        lineas.append("  (ninguno)")

    lineas += ["=" * 60, ""]

    with open(REPORTE_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    print(f"[INFO] Reporte generado: {REPORTE_TXT}")

def main():
    fecha_ejecucion = datetime.datetime.now()
    archivo_origen  = str(DATA_FILE.relative_to(PROJECT_ROOT))

    df_raw = leer_y_limpiar_csv(DATA_FILE)
    filas_leidas = len(df_raw)

    df_validos, errores = validar(df_raw)
    filas_cargadas   = len(df_validos)
    filas_rechazadas = len(errores)
    estado = "FINALIZADO_CON_ERRORES" if errores else "FINALIZADO_OK"
    dimaps = construir_dimensiones(df_validos)

    print(f"[INFO] Conectando a MySQL {DB_HOST}:{DB_PORT} / {DB_NAME} …")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4"
        )
    except mysql.connector.Error as e:
        print(f"[ERROR] No se pudo conectar a MySQL: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    try:
        crear_tablas(cursor)

        truncar_tablas(cursor)

        cargar_dimensiones(cursor, dimaps)

        cargar_fact(cursor, df_validos, dimaps)

        cargar_errores(cursor, errores, archivo_origen, fecha_ejecucion)

        cargar_log(cursor, archivo_origen, fecha_ejecucion,
                   filas_leidas, filas_cargadas, filas_rechazadas, estado)

        conn.commit()
        print("[INFO] Transacción confirmada (COMMIT).")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Fallo durante la carga — ROLLBACK: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

    generar_reporte(fecha_ejecucion, archivo_origen,
                    filas_leidas, filas_cargadas, filas_rechazadas,
                    estado, errores)
    print()
    print("=" * 45)
    print("   RESUMEN DE EJECUCIÓN ETL")
    print("=" * 45)
    print(f"  Filas leidas     : {filas_leidas}")
    print(f"  Filas cargadas   : {filas_cargadas}")
    print(f"  Filas rechazadas : {filas_rechazadas}")
    print(f"  Estado           : {estado}")
    print("=" * 45)


if __name__ == "__main__":
    main()
