"""Presentación común de diagramas: lienzo 1200 x 800 sin deformar el contenido."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 1200, 800
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


def guardar(nombre: str, fuente: str | bytes) -> None:
    contenido = ET.fromstring(fuente)
    if "viewBox" not in contenido.attrib:
        raise ValueError("El SVG debe incluir viewBox para conservar sus proporciones")
    contenido.set("x", "24")
    contenido.set("y", "24")
    contenido.set("width", str(WIDTH - 48))
    contenido.set("height", str(HEIGHT - 48))
    contenido.set("preserveAspectRatio", "xMidYMid meet")
    raiz = ET.Element(f"{{{NS}}}svg", {
        "width": str(WIDTH), "height": str(HEIGHT),
        "viewBox": f"0 0 {WIDTH} {HEIGHT}",
    })
    ET.SubElement(raiz, f"{{{NS}}}rect", {
        "width": str(WIDTH), "height": str(HEIGHT), "fill": "white",
    })
    raiz.append(contenido)
    svg = OUT / f"{nombre}.svg"
    ET.ElementTree(raiz).write(svg, encoding="utf-8", xml_declaration=True)
    subprocess.run(["rsvg-convert", "-o", str(OUT / f"{nombre}.png"), str(svg)], check=True)
