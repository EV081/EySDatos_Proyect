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
  subgraph cluster_local {{
    label=<<b>Tu dispositivo (confiable)</b>>; labeljust=l; style="rounded,filled,dashed";
    color="{VERDE}"; fillcolor="{VERDE_F}"; fontcolor="{VERDE}"; penwidth=1.6;
    front [label=<<b>Frontend</b><br/>muestra el texto plano>, color="{VERDE}", fillcolor="white"];
    cli [label=<<b>Cliente local</b><br/>llaves, cifrado y handshake<br/>desbloqueo con contraseña + TOTP>, color="{VERDE}", fillcolor="white"];
    boveda [label=<<b>Bóveda cifrada</b><br/>llave privada + historial<br/>Argon2id + AES-256-GCM>, shape=cylinder, style="filled", color="{VERDE}", fillcolor="white"];
    {{ rank=same; front; cli; boveda; }}
    front -> cli [label="API local\\n(127.0.0.1)", dir=both, color="{VERDE}", fontcolor="{VERDE}"];
    cli -> boveda [color="{VERDE}"];
  }}
  subgraph cluster_remoto {{
    label=<<b>Servicios remotos (no confiables)</b>>; labeljust=l; labelloc=b; style="rounded,filled,dashed";
    color="{ROJO}"; fillcolor="{ROJO_F}"; fontcolor="{ROJO}"; penwidth=1.6;
    dir [label=<<b>Directorio de llaves</b><br/>API de llaves y verificación de MFA<br/>PostgreSQL alojado en Supabase>, color="{ROJO}", fillcolor="white"];
    dis [label=<<b>Discord</b><br/>un bot por persona, canal privado<br/>solo ve texto cifrado y metadatos>, color="{ROJO}", fillcolor="white"];
    {{ rank=same; dir; dis; }}
  }}
  cli -> dir [label="TLS 1.3 + CA propia\\nllaves y validación del segundo factor", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  cli -> dis [label="handshake (hs1-hs3)\\ny mensajes cifrados", dir=both, color="{NARANJA}", fontcolor="{NARANJA}"];
  nota [shape=note, style=filled, fillcolor="{GRIS_F}", color="{GRIS}", fontcolor="{GRIS}",
        label="Las llaves privadas permanecen en el dispositivo.\\nLa contraseña maestra y el historial no se envían al directorio."];
  cli -> nota [style=invis];
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
  ok  [label=<<b>Sí: verificado</b><br/>se guarda un pin de la llave pública>, color="{VERDE}", fillcolor="{VERDE_F}"];
  no  [label=<<b>No: no verificar</b><br/>posible sustitución de llaves>, color="{ROJO}", fillcolor="{ROJO_F}"];
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
  local [label=<<b>Dispositivo de la persona</b><br/>Frontend + cliente local<br/>vault.json y store.enc cifrados>, color="{VERDE}", fillcolor="{VERDE_F}"];
  ec2 [label=<<b>Directorio en AWS EC2</b><br/>Virginia del Norte: us-east-1<br/>Registro, consultas y validación MFA<br/>Clave de cifrado TOTP fuera de la base>, color="{ROJO}", fillcolor="{ROJO_F}"];
  discord [label=<<b>Discord</b><br/>Canal privado con bots<br/>Texto cifrado + metadatos>, color="{ROJO}", fillcolor="{ROJO_F}"];
  base [label=<<b>PostgreSQL en Supabase</b><br/>ID, llave pública, fechas y aviso<br/>TOTP cifrado + hashes de recuperación<br/>Región del proyecto por confirmar>, shape=cylinder, color="{ROJO}", fillcolor="{ROJO_F}"];
  copias [label=<<b>Registros y respaldos</b><br/>Auditoría: IDs seudonimizados, 90 días<br/>Copias cifradas: 30 días<br/>Clave TOTP: respaldo separado<br/>Destino externo por comprobar>, shape=cylinder, color="{NARANJA}", fillcolor="{NARANJA_F}"];
  {{ rank=same; ec2; discord; }}
  {{ rank=same; base; copias; }}
  local -> ec2 [label="TLS 1.3\\nregistro, ARCO y desbloqueo MFA", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  local -> discord [label="handshake y mensajes cifrados", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  ec2 -> base [label="PostgreSQL + TLS\\nrol de mínimos permisos", dir=both, color="{AZUL}", fontcolor="{AZUL}"];
  ec2 -> copias [label="auditoría del servicio", color="{NARANJA}", fontcolor="{NARANJA}"];
  base -> copias [label="copias cifradas", color="{NARANJA}", fontcolor="{NARANJA}"];
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
