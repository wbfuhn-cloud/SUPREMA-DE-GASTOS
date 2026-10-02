# Inversiones IA 3.0 — Fase 1 aprobada

Fecha: 2026-10-01.

## Cambios realizados

- Navegación de pestañas unificada en `activateTab`.
- “Mi Portafolio” dejó de tratarse como pestaña sin `data-tab`.
- Roles ARIA, selección, foco y navegación por flechas añadidos.
- “Cazador de Gemas” e “IA Adaptativa” abren su panel correcto.
- Contrato muerto `/api/prices/history` retirado del cliente.
- Confirmaciones nativas sustituidas por diálogo accesible.
- Mensajes de éxito/error sustituidos por región de avisos accesible.
- Confianza histórica sin evidencia cambia de 50% ficticio a `N/D`.
- Fallback del predictor ya no presenta el score heurístico como ML.
- Score heurístico, score ML y confianza histórica se presentan separados.
- Estado ML dejó de exponer rutas absolutas locales.
- Campos de riesgo asociados a sus etiquetas.
- Prueba externa Gemini aislada y sin impresión de secretos (Fase 0).

## Evidencia de aprobación

| Criterio | Resultado |
|---|---|
| 100 cambios alternados de pestaña | Aprobado; un panel activo y 0 errores |
| Gemas visible | Aprobado en navegador real |
| IA Adaptativa visible | Aprobado en navegador real |
| Navegación por teclado | ArrowRight selecciona IA Adaptativa |
| Confirmación accesible | Abre y cancela sin ejecutar la acción |
| Consola | 0 errores/warnings en recorrido validado |
| Estados IA sin muestras | `N/D`, verificadas 0, ajustes 0 |
| Separación heurística/ML | RUM muestra `Score ML N/D (solo heurística)` |
| Endpoint ML | No contiene `db_path` ni `model_path` |
| Campos accesibles | 0 inputs/selects sin label o aria-label |
| Pruebas de Fase 1 | 6/6 aprobadas |
| Sintaxis JavaScript | `node --check` aprobado |
| Compilación Python | `compileall` aprobado |
| Integridad Git | `git diff --check` aprobado |

## Pruebas reproducibles

```powershell
C:\Users\OMEN\Desktop\SUPREMA-DE-GASTOS-main\.venv\Scripts\python.exe -B tests\test_inversiones_phase1.py
node --check tools\NOTIFICADOR_BOT\app.js
C:\Users\OMEN\Desktop\SUPREMA-DE-GASTOS-main\.venv\Scripts\python.exe -B -m compileall -q src tools\NOTIFICADOR_BOT tests
```

## Resultado

La interfaz ya no confunde ausencia de evidencia con 50% de confianza ni una
heurística con inferencia ML. Los flujos visibles de pestañas, confirmación,
estado vacío y error quedan funcionales y verificables.
