# Mensajería cifrada sobre Discord

Cada persona ejecuta el cliente y el frontend en su computadora. El directorio de llaves se aloja en EC2, Virginia del Norte (`us-east-1`), y PostgreSQL está en Supabase. Las copias cifradas se guardan en S3, en la misma región que EC2. El MFA del registro y del desbloqueo está desplegado y probado con Microsoft Authenticator.

Para instalar y usar el proyecto desde cero:

- [Ejecutar la aplicación: `.env`, Discord, Authenticator, `make client` y `make frontend`](docs/ejecucion-local.md).
- [Instalar el directorio en EC2, preparar Supabase y configurar las copias en S3](docs/despliegue-ec2.md).

El [informe](docs/README.md) explica el diseño y sus límites. La [DPIA](docs/dpia/DPIA.md) revisa los riesgos para los datos personales. La [tabla de trazabilidad](docs/trazabilidad.md) relaciona cada requerimiento con sus pruebas; GitHub Actions revisa que esté actualizada.

Las revisiones cruzadas del equipo y la revisión humana del protocolo están finalizadas. La aprobación de la DPIA consta en su paso 7, con los correos de Elmer Villegas Suarez y Farid Aquino Castro como firma del equipo.

Las [políticas de uso seguro](docs/politicas/uso-seguro.md) y el [plan de respuesta a incidentes](docs/politicas/respuesta-incidentes.md) describen la operación del servicio. El [aviso](docs/privacidad/aviso-de-privacidad.md) y la [política de privacidad](docs/privacidad/politica-de-privacidad.md) explican el tratamiento de datos y cómo ejercer los derechos.
