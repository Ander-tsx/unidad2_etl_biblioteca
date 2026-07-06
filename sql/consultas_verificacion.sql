-- 1. ¿Cuántos registros hay en fact_prestamos?
SELECT COUNT(*) AS total_registros_fact_prestamos
FROM fact_prestamos;

-- ============================================================

-- 2. ¿Cuántos registros hay en etl_errores?
SELECT COUNT(*) AS total_errores
FROM etl_errores;

-- ============================================================

-- 3. ¿Qué errores fueron registrados?
SELECT
    id_error,
    fecha_error,
    fila_csv,
    id_registro       AS id_prestamo,
    descripcion_error
FROM etl_errores
ORDER BY id_error;

-- ============================================================

-- 4. ¿Cuál fue el último estado registrado en etl_log?
SELECT
    id_log,
    fecha_ejecucion,
    archivo_origen,
    filas_leidas,
    filas_cargadas,
    filas_rechazadas,
    estado
FROM etl_log
ORDER BY id_log DESC
LIMIT 1;

-- ============================================================

-- 5. Total de multas por carrera
SELECT
    c.carrera,
    COUNT(f.id_prestamo)   AS total_prestamos,
    SUM(f.total_multa)     AS total_multas
FROM fact_prestamos f
JOIN dim_carrera c ON f.id_carrera = c.id_carrera
GROUP BY c.carrera
ORDER BY total_multas DESC;

-- ============================================================

-- 6. Total de multas por categoría de libro
SELECT
    l.categoria,
    COUNT(f.id_prestamo)   AS total_prestamos,
    SUM(f.total_multa)     AS total_multas
FROM fact_prestamos f
JOIN dim_libro l ON f.id_libro = l.id_libro
GROUP BY l.categoria
ORDER BY total_multas DESC;

-- ============================================================

-- 7. Promedio de días de préstamo por sede
SELECT
    s.sede,
    COUNT(f.id_prestamo)          AS total_prestamos,
    ROUND(AVG(f.dias_prestamo), 2) AS promedio_dias_prestamo
FROM fact_prestamos f
JOIN dim_sede s ON f.id_sede = s.id_sede
GROUP BY s.sede
ORDER BY promedio_dias_prestamo DESC;

-- ============================================================

-- 8. Los 5 libros con mayor total de multa
SELECT
    l.libro,
    l.categoria,
    COUNT(f.id_prestamo) AS veces_prestado,
    SUM(f.total_multa)   AS total_multa_acumulada
FROM fact_prestamos f
JOIN dim_libro l ON f.id_libro = l.id_libro
GROUP BY l.libro, l.categoria
ORDER BY total_multa_acumulada DESC
LIMIT 5;

-- ============================================================

-- 9. Préstamos detallados con fecha, alumno, carrera,
--    libro, categoría, sede y total de multa
SELECT
    fe.fecha                  AS fecha_prestamo,
    a.alumno,
    c.carrera,
    l.libro,
    l.categoria,
    s.sede,
    f.dias_prestamo,
    f.multa_diaria,
    f.total_multa
FROM fact_prestamos f
JOIN dim_fecha   fe ON f.id_fecha   = fe.id_fecha
JOIN dim_alumno   a ON f.id_alumno  = a.id_alumno
JOIN dim_carrera  c ON f.id_carrera = c.id_carrera
JOIN dim_libro    l ON f.id_libro   = l.id_libro
JOIN dim_sede     s ON f.id_sede    = s.id_sede
ORDER BY fe.fecha, a.alumno;

-- ============================================================

-- 10. Conteo de préstamos por sede
SELECT
    s.sede,
    COUNT(f.id_prestamo) AS total_prestamos
FROM fact_prestamos f
JOIN dim_sede s ON f.id_sede = s.id_sede
GROUP BY s.sede
ORDER BY total_prestamos DESC;
