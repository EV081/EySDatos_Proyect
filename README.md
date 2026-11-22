# Mensajería cifrada sobre Discord

Cada persona ejecuta el cliente y el frontend en su computadora. El directorio de llaves se aloja en EC2, Virginia del Norte (`us-east-1`), y PostgreSQL está en Supabase. Las copias cifradas se guardan en S3, en la misma región que EC2. Desplegamos y probamos el MFA del registro y del desbloqueo con Microsoft Authenticator.

Para instalar y usar el proyecto desde cero:

- [Ejecutar la aplicación: `.env`, Discord, Authenticator, `make client` y `make frontend`](docs/guia/ejecucion-local.md).
- [Instalar el directorio en EC2, preparar Supabase y configurar las copias en S3](docs/guia/despliegue-ec2.md).

Elige la plantilla según dónde vayas a ejecutar el proyecto y cópiala a `.env`:

| Plantilla | Entorno |
|---|---|
| [`.env.example.local`](.env.example.local) | Laptop: cliente, bot propio y conexión al directorio de EC2 |
| [`.env.example.ec2`](.env.example.ec2) | EC2: directorio, Supabase, OAuth y respaldos en S3 |
| [`.env.example`](.env.example) | Desarrollo y pruebas con directorio y PostgreSQL locales |

El [informe](docs/README.md) resume el proyecto completo y la [primera entrega](docs/primera-entrega.md) detalla el diseño y sus límites. La [DPIA](docs/dpia/DPIA.md) revisa los riesgos para los datos personales. La [tabla de trazabilidad](docs/trazabilidad/trazabilidad.md) relaciona cada requerimiento con sus pruebas; GitHub Actions revisa que esté actualizada.

Completamos la revisión cruzada del proyecto y la revisión del protocolo. Aprobamos la DPIA y consignamos nuestros correos como firma en el paso 7.

Las [políticas de uso seguro](docs/politicas/uso-seguro.md) y el [plan de respuesta a incidentes](docs/politicas/respuesta-incidentes.md) describen la operación del servicio. El [aviso](docs/privacidad/aviso-de-privacidad.md) y la [política de privacidad](docs/privacidad/politica-de-privacidad.md) explican el tratamiento de datos y cómo ejercer los derechos.
