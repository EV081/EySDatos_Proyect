# Experimento: utilidad frente a privacidad diferencial

Generado con `python -m ops.dp.experiment --repeticiones 1000` sobre datos sintéticos. Cada fila es el ε del
reporte completo; cada una de las 3 consultas recibe ε/3. Mecanismo: Laplace discreto de OpenDP.
Los valores cambian un poco en cada ejecución porque el ruido es aleatorio.

## A. Tendencia de registros (12 semanas, 182 personas, pico de 30)

| ε del reporte | ε de la consulta | Error medio por semana (personas) | Error relativo del total | Pico a ±1 semana |
|---|---|---|---|---|
| 0.1 | 0.033 | 20.8 | 68 % | 38 % |
| 0.5 | 0.167 | 5.5 | 12 % | 82 % |
| 1 | 0.333 | 2.8 | 6 % | 96 % |
| 2 | 0.667 | 1.4 | 3 % | 100 % |
| 5 | 1.667 | 0.4 | 1 % | 100 % |

## B. Grupo pequeño (3 personas con un aviso viejo frente a 45)

| ε del reporte | Error relativo del grupo pequeño | Veces que el reporte dice 0 |
|---|---|---|
| 0.1 | 522 % | 48 % |
| 0.5 | 139 % | 32 % |
| 1 | 77 % | 21 % |
| 2 | 43 % | 9 % |
| 5 | 13 % | 1 % |

## C. Detección de abuso con ruido (umbral 20, sensibilidad 2)

| ε del reporte | Detecta un ataque de 20 eventos | Alerta falsa con 10 eventos |
|---|---|---|
| 0.1 | 49 % | 42 % |
| 0.5 | 51 % | 23 % |
| 1 | 56 % | 9 % |
| 2 | 60 % | 3 % |
| 5 | 68 % | 0 % |
