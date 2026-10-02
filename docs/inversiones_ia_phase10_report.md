# Fase 10 — UX de confianza, aprendizaje y explicación

## Resultado

Se implementó un contrato de explicación por señal y un panel operativo que separa heurística, ML y Fourier. Ninguna ausencia se representa como cero o 50 %: se muestra `N/D` con su razón. ML y Fourier permanecen visibles como experimentales e inactivos para decisiones.

## Controles implementados

- Señal, horizonte, timestamp, frescura, precio y proveedor.
- Probabilidad calibrada separada del score heurístico y del módulo espectral.
- Calidad, incertidumbre, factores a favor/en contra e invalidación.
- Stop, objetivo, tamaño por riesgo y versiones de modelo/reglas.
- Descargo explícito de no garantía y no asesoría financiera.
- Estado de entrenamiento, dataset, evidencia fuera de muestra, calibración, drift y degradación.
- Filtros de historial por fecha, ticker, modelo, señal, horizonte y resultado.
- Componentes con etiquetas semánticas y navegación por teclado preservada.

## Pendientes de aprobación empírica

La implementación técnica está terminada. Comprensión ≥80 %, WCAG 2.1 AA y LCP/interacción deben medirse con usuarios, auditoría de accesibilidad y telemetría en la red objetivo; no se declaran aprobados sin esas mediciones.
