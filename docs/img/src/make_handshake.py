"""Genera flujo-handshake.svg/.png (diagrama del handshake autenticado y de la mensajería)."""
import subprocess, html
W, H = 1180, 860
XA, XD, XB = 235, 590, 945
out = []
def e(s): return html.escape(s, quote=False)
def text(x, y, s, size=14, anchor="middle", color="#1f2937", weight="normal"):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}">{e(s)}</text>')
def box(x, y, w, h, fill, stroke, lines, size=13, align="middle"):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    ly = y + 22
    for ln in lines:
        tx = x + w/2 if align == "middle" else x + 12
        text(tx, ly, ln, size, align if align != "middle" else "middle")
        ly += size + 6
def arrow(x1, x2, y, label_lines, color, both=False):
    mk = 'marker-end="url(#a)"'
    ms = 'marker-start="url(#as)"' if both else ''
    out.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="2.2" {mk} {ms}/>')
    cy = y - 10 - (len(label_lines) - 1) * 17
    for ln in label_lines:
        text((x1 + x2) / 2, cy, ln, 13, "middle", color, "bold"); cy += 17

out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="DejaVu Sans, Arial, sans-serif">')
out.append('<defs><marker id="a" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker>'
           '<marker id="as" markerWidth="10" markerHeight="10" refX="1" refY="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker></defs>')
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
# lanes
for x, t1, t2, fill, st in [(XA, "ALICE (cliente A)", "inicia la sesión", "#dbeafe", "#1d4ed8"),
                            (XD, "DISCORD", "solo transporta y persiste bytes", "#ede9fe", "#6d28d9"),
                            (XB, "BOB (cliente B)", "responde", "#d1fae5", "#047857")]:
    out.append(f'<rect x="{x-130}" y="14" width="260" height="56" rx="12" fill="{fill}" stroke="{st}" stroke-width="2"/>')
    text(x, 38, t1, 16, "middle", st, "bold"); text(x, 58, t2, 12, "middle", "#374151")
    out.append(f'<line x1="{x}" y1="70" x2="{x}" y2="{H-120}" stroke="{st}" stroke-width="1.5" stroke-dasharray="6 6"/>')
# step 0
box(XA-175, 90, 350, 56, "#f8fafc", "#64748b", ["0. Obtiene pk_B del directorio (TLS 1.3)", "y la compara con el pin guardado"])
box(XB-175, 90, 350, 56, "#f8fafc", "#64748b", ["0. Obtiene pk_A del directorio (TLS 1.3)", "y la compara con el pin guardado"])
# hs1
arrow(XA, XB, 192, ["1. hs1:  ids, sid, R_A, epk_A = g^a"], "#1d4ed8")
box(XB-205, 208, 410, 104, "#ecfdf5", "#047857",
    ["Bob genera b efímero y R_B; calcula g^ab y destruye b", "T = ids ‖ sid ‖ R_A ‖ R_B ‖ epk_A ‖ epk_B ‖ versión",
     "PRK = HKDF(g^ab, sal = SHA-256(T)) → K_AB, K_BA, K_conf", "σ_B = Sign_B(ctx_resp ‖ T);  tag_B = HMAC(K_conf, \"B\" ‖ H(T))"], 12)
# hs2
arrow(XB, XA, 354, ["2. hs2:  R_B, epk_B = g^b, σ_B, tag_B"], "#047857")
box(XA-205, 372, 410, 122, "#eff6ff", "#1d4ed8",
    ["Alice verifica σ_B con pk_B  → si falla: ABORTA",
     "Deriva las mismas claves (g^ab = (g^b)^a)", "Verifica tag_B (confirmación de clave)",
     "σ_A = Sign_A(ctx_ini ‖ T);  tag_A = HMAC(K_conf, \"A\" ‖ H(T))",
     "Destruye a (efímero): sin él, el pasado no se recupera"], 12)
# hs3
arrow(XA, XB, 536, ["3. hs3:  σ_A, tag_A"], "#1d4ed8")
box(XB-205, 552, 410, 78, "#ecfdf5", "#047857",
    ["Bob verifica σ_A con pk_A y tag_A → si falla: ABORTA", "Si todo valida  →  SESIÓN ACTIVA (PFS en ambos lados)"], 12)
# messages
arrow(XA, XB, 672, ["4. msg:  sid, ctr, nonce, AES-256-GCM(K_AB, m; AAD)"], "#b45309", both=False)
arrow(XB, XA, 712, ["4'. msg:  sid, ctr, nonce, AES-256-GCM(K_BA, m; AAD)"], "#b45309")
# footer
out.append(f'<rect x="20" y="{H-102}" width="{W-40}" height="84" rx="10" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/>')
text(W/2, H-78, "ctx_ini ≠ ctx_resp (separación de dominio y roles asimétricos: evita reflexión y oráculo de firma).  Las firmas cubren ids, nonces y ambas llaves efímeras.", 12.5)
text(W/2, H-56, "Claves distintas por dirección (K_AB, K_BA) y contador ctr por dirección: un mensaje no puede reflejarse ni repetirse.  AAD = sid ‖ emisor ‖ receptor ‖ ctr.", 12.5)
text(W/2, H-34, "Tras 3 y 4, el robo de la llave de identidad no descifra el tráfico grabado: las llaves efímeras a, b ya no existen (PFS).", 12.5, "middle", "#b91c1c", "bold")
out.append('</svg>')
open("flujo-handshake.svg", "w").write("\n".join(out))
subprocess.run(["rsvg-convert", "-z", "1.5", "-o", "flujo-handshake.png", "flujo-handshake.svg"], check=True)
