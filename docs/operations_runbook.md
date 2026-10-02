# Runbook de operación — Inversiones IA 3.0

## Alertas y correlación

Toda respuesta incluye `X-Correlation-ID`. Consultar `/api/bolsa/operations` para latencia, errores, datos vencidos, señales y discrepancias. Una alerta crítica debe incluir endpoint, ID, primera ocurrencia, impacto y acción recomendada.

## Kill switch

Ante pérdida fuera de límite, datos corruptos, drift severo o proveedor caído, activar el kill switch autenticado. El escaneo y la observación continúan, pero toda decisión queda en `SIN SEÑAL`. Registrar operador y motivo.

## Proveedor caído

Activar kill switch, conservar último dato como vencido y no ejecutable, abrir incidente crítico, cambiar al proveedor secundario y validar timestamps antes de cerrar.

## Datos corruptos

Aislar el lote, activar kill switch, conservar hashes y logs, restaurar desde respaldo cifrado y ejecutar validaciones de esquema y calidad.

## Modelo no disponible

Mantener ML y Fourier inactivos. El sistema puede observar y mostrar heurística, pero no generar compras sin el gate aprobado.

## Base bloqueada

Detener escrituras, conservar lecturas si son consistentes, copiar evidencia, recuperar la última copia cifrada. Objetivos: RTO 30 min y RPO 15 min.

## Canary y rollback

Desplegar a una fracción controlada sin dinero real, comparar salud durante 30 minutos y promover solo con aprobación humana. Para rollback, redeplegar el tag anterior firmado, restaurar configuración compatible y validar health/readiness. Objetivo del simulacro: menos de 10 minutos.

## Respaldos

Respaldar predicciones y portafolio cada 15 minutos, cifrar con una clave gestionada fuera del repositorio, retener 35 días y probar restauración mensualmente.
