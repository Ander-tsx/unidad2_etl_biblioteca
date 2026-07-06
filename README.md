# ETL Biblioteca — Unidad 2

**Autor:** Gaspar Andres Garcia Quiroz  
**Grupo:** 9A  
**Materia:** Extracción de conocimiento de Bases de Datos 9°A

---

## 1. Objetivo del proyecto

Implementar un proceso ETL completo sobre un dataset de 100 préstamos de
biblioteca. El flujo convierte el CSV crudo en un mini Data Warehouse en
MySQL (`biblioteca_dw`), detectando y registrando errores de forma
controlada, y generando evidencias automáticas de cada ejecución.

---

## 2. Requisitos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.9+ |
| MySQL Server | 8.0+ (puerto **3307**) |
| pip | cualquier versión reciente |

**Librerías Python:**

```
pandas
mysql-connector-python
python-dotenv
```

---

## 3. Crear la base de datos en MySQL

Conéctate a MySQL (por ejemplo desde DataGrip o la terminal) y ejecuta:

```sql
CREATE DATABASE IF NOT EXISTS biblioteca_dw
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

> El script crea las tablas automáticamente en la primera ejecución.

---

## 4. Configurar variables de entorno

Copia el archivo de ejemplo y edita con tus credenciales reales:

```bash
cp .env.example .env
```

Contenido de `.env`:

```
DB_HOST=localhost
DB_PORT=3307
DB_USER=tu_usuario
DB_PASSWORD=tu_password
DB_NAME=biblioteca_dw
NOMBRE_ALUMNO=Gaspar Andres Garcia Quiroz
GRUPO=9A
```


---

## 5. Instalar librerías

```bash
pip install pandas mysql-connector-python python-dotenv
```

---

## 6. Ejecutar el ETL

Desde la **raíz del repositorio** (`unidad2_etl_biblioteca/`):

```bash
python scripts/etl_biblioteca.py
```

Para generar el archivo de texto con las evidencias:

```bash
python scripts/generar_evidencias.py
```

---

## 7. Resultado esperado

```
[INFO] Leyendo archivo: data/prestamos_biblioteca_100.csv
[INFO] Filas leídas del CSV: 100
[INFO] Registros válidos : 98
[INFO] Registros con error: 2
[INFO] Conectando a MySQL localhost:3307 / biblioteca_dw …
[INFO] Tablas verificadas / creadas correctamente.
[INFO] Tablas truncadas (excepto etl_log).
[INFO] Dimensiones cargadas.
[INFO] fact_prestamos cargada: 98 registros.
[INFO] etl_errores cargada: 2 registros.
[INFO] etl_log actualizado.
[INFO] Transacción confirmada (COMMIT).
[INFO] Reporte generado: evidencias/reporte_ejecucion.txt

=============================================
   RESUMEN DE EJECUCIÓN ETL
=============================================
  Filas leidas     : 100
  Filas cargadas   : 98
  Filas rechazadas : 2
  Estado           : FINALIZADO_CON_ERRORES
=============================================
```

**Errores detectados:**

| id_prestamo | Tipo de error |
|---|---|
| 5099 | `total_multa` incorrecto (valor=40, esperado=70) |
| 5002 | `id_prestamo` duplicado (segunda aparición) |
