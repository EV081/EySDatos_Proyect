# Mensajería cifrada sobre Discord

Cada persona ejecuta el cliente y el frontend en su computadora. El directorio de llaves se aloja en EC2, Virginia del Norte (`us-east-1`), y PostgreSQL está en Supabase.

Las dos guías operativas son:

- [Ejecutar la aplicación: `.env`, Discord, Authenticator, `make client` y `make frontend`](docs/ejecucion-local.md).
- [Desplegar y actualizar el directorio en EC2 con PostgreSQL en Supabase](docs/despliegue-ec2.md).

El informe y la DPIA están en `docs/`. La tabla de trazabilidad es evidencia generada de la entrega; la CI comprueba que coincida con los requerimientos y las pruebas.
