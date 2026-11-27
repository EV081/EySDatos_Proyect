"""Genera los diagramas de arquitectura, registro, verificación y tratamiento de datos.

Uso:  python3 docs/img/src/make_diagramas.py
Requiere `dot` y `rsvg-convert`. Escribe SVG y PNG en docs/img/.
"""
import pathlib
import subprocess
from formato_diagramas import guardar

OUT = pathlib.Path(__file__).resolve().parent.parent

FONT = "Noto Sans"
VERDE, VERDE_F = "#0f7b55", "#e8f7f0"
ROJO, ROJO_F = "#b42318", "#fdecea"
AZUL, AZUL_F = "#1d4ed8", "#e8f0ff"
NARANJA, NARANJA_F = "#b45309", "#fff4e0"
GRIS, GRIS_F = "#475467", "#f4f5f7"

BASE = f"""
  graph [fontname="{FONT}", fontsize=13, pad=0.3, bgcolor="white", nodesep=0.5, ranksep=1.0];
  node  [fontname="{FONT}", fontsize=12, shape=box, style="rounded,filled", penwidth=1.6, margin="0.2,0.12"];
  edge  [fontname="{FONT}", fontsize=11, penwidth=1.6, color="{GRIS}", fontcolor="{GRIS}"];
"""

ARQUITECTURA = f"""
digraph G {{
  rankdir=TB;
  {BASE}
  graph [nodesep=0.3, ranksep=0.5];
  subgraph cluster_local {{
    label=<<b>Dispositivo de cada persona</b>>; labeljust=l; style="rounded,filled,dashed";
    color="{VERDE}"; fillcolor="{VERDE_F}"; fontcolor="{VERDE}";
    front [label=<<b>Frontend</b><br/>interfaz y texto plano>, color="{VERDE}", fillcolor="white"];
    cli [label=<<b>Cliente local</b><br/>cifrado, identidad y sesiones<br/>contraseña + TOTP al desbloquear>, color="{VERDE}", fillcolor="white"];
    boveda [label=<<b>Bóveda de identidad</b><br/>llave privada + clave del almacén<br/>Argon2id + AES-256-GCM>, shape=cylinder, style=filled, color="{VERDE}", fillcolor="white"];
    store [label=<<b>Almacén local</b><br/>historial, contactos y cola<br/>AES-256-GCM>, shape=cylinder, style=filled, color="{VERDE}", fillcolor="white"];
    {{ rank=same; front; cli; }}
    {{ rank=same; boveda; store; }}
    front -> cli [label="API local\\n127.0.0.1", dir=both, color="{VERDE}", fontcolor="{VERDE}"];
    cli -> boveda [dir=both, color="{VERDE}"];
    cli -> store [dir=both, color="{VERDE}"];
  }}
  dir [label=<<b>Directorio en AWS EC2</b><br/>Llaves públicas y validación MFA<br/>Virginia del Norte: us-east-1>, color="{AZUL}", fillcolor="{AZUL_F}"];
  backup [label=<<b>Respaldo desde EC2</b><br/>pg_dump con rol de solo lectura<br/>AES-256-GCM antes de subir>, color="{NARANJA}", fillcolor="{NARANJA_F}"];
  db [label=<<b>PostgreSQL · Supabase</b><br/>ID, llave pública, fechas y aviso<br/>TOTP cifrado y hashes de recuperación>, shape=cylinder, color="{AZUL}", fillcolor="{AZUL_F}"];
  s3 [label=<<b>Amazon S3 · us-east-1</b><br/>bucket privado: copias cifradas<br/>retención de 30 días>, shape=cylinder, color="{NARANJA}", fillcolor="{NARANJA_F}"];
  discord [label=<<b>Discord</b><br/>un bot por persona, canal privado<br/>texto cifrado + metadatos>, color="{ROJO}", fillcolor="{ROJO_F}"];
  {{ rank=same; dir; discord; }}
  {{ rank=same; db; backup; }}
  cli -> dir [label="TLS 1.3 + CA propia\\nllaves y validación MFA", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  cli -> discord [label="handshake y mensajes E2EE", dir=both, color="{ROJO}", fontcolor="{ROJO}"];
  dir -> db [label="PostgreSQL + TLS", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  db -> backup [label="pg_dump por TLS", color="{NARANJA}", fontcolor="{NARANJA}"];
  backup -> s3 [label="HTTPS: copia cifrada\\nverificación de tamaño y SHA-256", color="{NARANJA}", fontcolor="{NARANJA}"];
}}
"""

REGISTRO = f"""
digraph G {{
  rankdir=TB;
  {BASE}
  subgraph cluster_local {{
    label=<<b>Tu dispositivo</b>>; labeljust=l; style="rounded,filled,dashed";
    color="{VERDE}"; fillcolor="{VERDE_F}"; fontcolor="{VERDE}"; penwidth=1.6;
    a [label=<<b>1. Contraseña maestra</b><br/>la eliges al crear la identidad>, color="{VERDE}", fillcolor="white"];
    b [label=<<b>2. Se genera el par Ed25519</b><br/>llave privada + llave pública>, color="{VERDE}", fillcolor="white"];
    c [label=<<b>3. Se guarda la privada cifrada</b><br/>Argon2id + salt -&gt; AES-256-GCM>, shape=cylinder, style="filled", color="{NARANJA}", fillcolor="{NARANJA_F}"];
    {{ rank=same; a; b; c; }}
    a -> b; b -> c [label="nunca sale", fontcolor="{NARANJA}", color="{NARANJA}"];
  }}
  subgraph cluster_dir {{
    label=<<b>Directorio</b>>; labeljust=l; style="rounded,filled,dashed";
    color="{ROJO}"; fillcolor="{ROJO_F}"; fontcolor="{ROJO}"; penwidth=1.6;
    d [label=<<b>4. Prueba de posesión</b><br/>OAuth2 de Discord + código TOTP<br/>y firma de un nonce de un solo uso>, color="{ROJO}", fillcolor="white"];
    e [label=<<b>5. Registro guardado</b><br/>ID, llave pública, fechas<br/>aviso y datos privados del factor>, shape=cylinder, style="filled", color="{ROJO}", fillcolor="white"];
    {{ rank=same; d; e; }}
    d -> e [label="si la firma es válida", color="{VERDE}", fontcolor="{VERDE}"];
  }}
  b -> d [label="llave pública + prueba de posesión\\npor TLS 1.3", color="{AZUL}", fontcolor="{AZUL}"];
}}
"""

VERIFICACION = f"""
digraph G {{
  rankdir=TB;
  {BASE}
  alice [label=<<b>Alice</b><br/>huella = SHA-256(pk_A ‖ pk_B)<br/>60 dígitos en grupos de 5>, color="{AZUL}", fillcolor="{AZUL_F}"];
  bob   [label=<<b>Bob</b><br/>huella = SHA-256(pk_A ‖ pk_B)<br/>mismo orden, mismo resultado>, color="{VERDE}", fillcolor="{VERDE_F}"];
  cmp [label="Comparar fuera de Discord\\n¿Las dos huellas coinciden?", shape=diamond, style="filled", color="{NARANJA}", fillcolor="{NARANJA_F}"];
  ok  [label=<<b>Sí: verificado</b><br/>se guarda un pin de la llave pública<br/>solo ahora se puede conversar>, color="{VERDE}", fillcolor="{VERDE_F}"];
  no  [label=<<b>No: sin verificar</b><br/>no hay conversación<br/>posible sustitución de llaves>, color="{ROJO}", fillcolor="{ROJO_F}"];
  cambio [label=<<b>Si después la llave cambia</b><br/>se revoca la verificación, se aborta<br/>el handshake y se avisa a la persona>, color="{ROJO}", fillcolor="white", style="rounded,filled,dashed"];
  {{ rank=same; alice; bob; }}
  alice -> cmp [label="llamada o en persona"]; bob -> cmp [label="o código QR"];
  cmp -> ok [label="sí", color="{VERDE}", fontcolor="{VERDE}"];
  cmp -> no [label="no", color="{ROJO}", fontcolor="{ROJO}"];
  ok -> cambio [style=dashed];
}}
"""


DPIA = f"""
digraph G {{
  rankdir=TB;
  {BASE}
  graph [nodesep=0.4, ranksep=0.6];
  local [label=<<b>Dispositivo de la persona</b><br/>Frontend + cliente local<br/>Bóveda de identidad y almacén cifrados>, color="{VERDE}", fillcolor="{VERDE_F}"];
  ec2 [label=<<b>Directorio en AWS EC2</b><br/>Virginia del Norte: us-east-1<br/>Registro, consultas y validación MFA>, color="{AZUL}", fillcolor="{AZUL_F}"];
  discord [label=<<b>Discord</b><br/>Canal privado con bots<br/>Texto cifrado + metadatos>, color="{ROJO}", fillcolor="{ROJO_F}"];
  base [label=<<b>PostgreSQL en Supabase</b><br/>ID, llave pública, fechas y aviso<br/>TOTP cifrado + hashes de recuperación<br/>Región del proyecto por confirmar>, shape=cylinder, color="{AZUL}", fillcolor="{AZUL_F}"];
  backup [label=<<b>Respaldo desde EC2</b><br/>Lectura de la base con permisos mínimos<br/>Cifrado AES-256-GCM antes de subir>, color="{NARANJA}", fillcolor="{NARANJA_F}"];
  audit [label=<<b>Auditoría en EC2</b><br/>IDs seudonimizados, sin contenido<br/>Retención: 90 días>, shape=cylinder, color="{GRIS}", fillcolor="{GRIS_F}"];
  s3 [label=<<b>Amazon S3 · us-east-1</b><br/>Bucket privado, copias cifradas<br/>Retención: 30 días>, shape=cylinder, color="{NARANJA}", fillcolor="{NARANJA_F}"];
  {{ rank=same; ec2; discord; }}
  {{ rank=same; base; audit; }}
  local -> ec2 [label="TLS 1.3: registro, ARCO y MFA", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  local -> discord [label="handshake y mensajes cifrados", dir=both, color="{ROJO}", fontcolor="{ROJO}"];
  ec2 -> base [label="PostgreSQL + TLS", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  ec2 -> audit [label="eventos del servicio", color="{GRIS}", fontcolor="{GRIS}"];
  base -> backup [label="pg_dump por TLS", color="{NARANJA}", fontcolor="{NARANJA}"];
  backup -> s3 [label="HTTPS: copia cifrada y verificada", color="{NARANJA}", fontcolor="{NARANJA}"];
}}
"""


def render(nombre, fuente):
    svg = subprocess.run(["dot", "-Tsvg"], input=fuente.encode(),
                         capture_output=True, check=True)
    guardar(nombre, svg.stdout)
    print("ok", nombre, "(SVG y PNG, 1200 x 800)")


if __name__ == "__main__":
    render("arquitectura", ARQUITECTURA)
    render("flujo-registro", REGISTRO)
    render("verificacion", VERIFICACION)
    render("dpia-tratamiento", DPIA)
