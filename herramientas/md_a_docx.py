"""Convierte INFORME_FINAL_PROYECTO_INTEGRADOR.md (subconjunto de Markdown) a Word (.docx) con formato académico.

Soporta: títulos #..####, párrafos, **negrita**, *cursiva*, `código`, [enlaces](url), listas con - y 1.,
tablas con |, bloques ``` y citas >. Agrega portada, índice (campo TOC: Word lo actualiza al abrir) y numeración
de páginas.
Uso: python herramientas/md_a_docx.py [entrada.md] [salida.docx]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

AZUL = RGBColor(0x0B, 0x3D, 0x5C)
GRIS = RGBColor(0x4A, 0x5B, 0x68)
FUENTE = "Calibri"


def sombrear(celda, color_hex: str) -> None:
    tcPr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color_hex)
    tcPr.append(shd)


def campo(parrafo, instruccion: str, texto: str = "") -> None:
    r = parrafo.add_run()
    for tipo, val in (("begin", None), ("instr", instruccion), ("separate", None), ("text", texto), ("end", None)):
        if tipo == "instr":
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = val; r._r.append(e)
        elif tipo == "text":
            e = OxmlElement("w:t"); e.text = val; r._r.append(e)
        else:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tipo); r._r.append(e)


INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def texto_rico(parrafo, texto: str, tam: float | None = None, color=None) -> None:
    for parte in INLINE.split(texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            r = parrafo.add_run(parte[2:-2]); r.bold = True
        elif parte.startswith("`") and parte.endswith("`"):
            r = parrafo.add_run(parte[1:-1]); r.font.name = "Consolas"; r.font.size = Pt((tam or 11) - 1)
            r.font.color.rgb = RGBColor(0x7A, 0x1F, 0x3D)
        elif parte.startswith("[") and "](" in parte:
            t, u = re.match(r"\[([^\]]+)\]\(([^)]+)\)", parte).groups()
            r = parrafo.add_run(t); r.font.color.rgb = RGBColor(0x0B, 0x5D, 0x8F); r.underline = True
        elif parte.startswith("*") and parte.endswith("*") and len(parte) > 2:
            r = parrafo.add_run(parte[1:-1]); r.italic = True
        else:
            r = parrafo.add_run(parte)
        if tam:
            r.font.size = Pt(tam)
        if color is not None:
            r.font.color.rgb = color


def estilos(doc: Document) -> None:
    st = doc.styles
    n = st["Normal"]; n.font.name = FUENTE; n.font.size = Pt(11)
    n.element.rPr.rFonts.set(qn("w:eastAsia"), FUENTE)
    n.paragraph_format.space_after = Pt(6); n.paragraph_format.line_spacing = 1.15
    for nivel, tam in ((1, 16), (2, 13.5), (3, 12), (4, 11)):
        h = st[f"Heading {nivel}"]
        h.font.name = FUENTE; h.font.size = Pt(tam); h.font.bold = True; h.font.color.rgb = AZUL
        h.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
        h.paragraph_format.space_before = Pt(14 if nivel <= 2 else 10); h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
    for s in ("List Bullet", "List Number"):
        st[s].font.name = FUENTE; st[s].font.size = Pt(11)


def tabla(doc: Document, filas: list[list[str]]) -> None:
    ncol = max(len(f) for f in filas)
    filas = [f + [""] * (ncol - len(f)) for f in filas]
    t = doc.add_table(rows=len(filas), cols=ncol)
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    ancho = Cm(16.5)
    largos = [max(4, max(len(f[j]) for f in filas)) for j in range(ncol)]
    largos = [min(x, 60) for x in largos]
    tot = sum(largos)
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            c = t.cell(i, j); c.width = int(ancho * largos[j] / tot)
            p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(0)
            texto_rico(p, v.strip(), tam=9, color=RGBColor(0xFF, 0xFF, 0xFF) if i == 0 else None)
            if i == 0:
                sombrear(c, "0B3D5C")
                for r in p.runs:
                    r.bold = True
            elif i % 2 == 0:
                sombrear(c, "EEF3F6")
    # repetir encabezado en cada página
    trPr = t.rows[0]._tr.get_or_add_trPr(); e = OxmlElement("w:tblHeader"); e.set(qn("w:val"), "true"); trPr.append(e)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def codigo(doc: Document, lineas: list[str]) -> None:
    t = doc.add_table(rows=1, cols=1); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.cell(0, 0); sombrear(c, "F3F5F7"); c.width = Cm(16.5)
    p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
    for k, l in enumerate(lineas):
        r = p.add_run(l); r.font.name = "Consolas"; r.font.size = Pt(7.5)
        if k < len(lineas) - 1:
            r.add_break()
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def portada(doc: Document, titulo: str, subtitulo: str, datos: list[str]) -> None:
    for _ in range(5):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Instituto Nacional de Estadística e Informática (INEI)"); r.font.size = Pt(13); r.font.color.rgb = GRIS
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Programa de Extensión Universitaria en Ciencia de Datos (PEU-CD)"); r.font.size = Pt(12); r.font.color.rgb = GRIS
    doc.add_paragraph(); doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(titulo); r.bold = True; r.font.size = Pt(22); r.font.color.rgb = AZUL
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(subtitulo); r.font.size = Pt(14); r.font.color.rgb = AZUL
    for _ in range(4):
        doc.add_paragraph()
    for d in datos:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        texto_rico(p, d, tam=11.5)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    h = doc.add_paragraph(); r = h.add_run("Contenido"); r.bold = True; r.font.size = Pt(16); r.font.color.rgb = AZUL
    campo(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u', "Haga clic derecho → «Actualizar campo» para generar el índice.")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def convertir(md: str, salida: Path) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = sec.bottom_margin = Cm(2.2)
    estilos(doc)
    pie = sec.footer.paragraphs[0]; pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pie.add_run("Proyecto integrador PEU-CD · INEI · página "); r.font.size = Pt(8.5); r.font.color.rgb = GRIS
    campo(pie, "PAGE", "1")
    lineas = md.splitlines()
    # portada: primeras líneas (# Informe…, ## Título, **Equipo**…) hasta el primer ---
    i = 0
    titulo = subtitulo = ""; datos = []
    while i < len(lineas) and lineas[i].strip() != "---":
        l = lineas[i].strip()
        if l.startswith("## "):
            titulo = l[3:]
        elif l.startswith("# "):
            subtitulo = l[2:]
        elif l:
            datos.extend(x.strip() for x in l.split(" · ") if x.strip())
        i += 1
    portada(doc, titulo, subtitulo, datos)
    i += 1
    tabla_buf, cod_buf, en_cod = [], [], False
    while i < len(lineas):
        l = lineas[i]
        s = l.strip()
        if s.startswith("```"):
            if en_cod:
                codigo(doc, cod_buf); cod_buf = []; en_cod = False
            else:
                en_cod = True
            i += 1; continue
        if en_cod:
            cod_buf.append(l); i += 1; continue
        if s.startswith("|"):
            celdas = [c for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r"\s*:?-{2,}:?\s*", c) for c in celdas):
                tabla_buf.append(celdas)
            i += 1
            if i >= len(lineas) or not lineas[i].strip().startswith("|"):
                tabla(doc, tabla_buf); tabla_buf = []
            continue
        if s == "---":
            i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            nivel = len(m.group(1))
            if nivel == 2 and s.startswith("## ") and "Resumen ejecutivo" not in s and i > 10:
                pass
            h = doc.add_heading(level=min(nivel, 4))
            texto_rico(h, m.group(2))
            i += 1; continue
        m = re.match(r"^(\s*)[-*]\s+(.*)", l)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            if len(m.group(1)) >= 2:
                p.paragraph_format.left_indent = Cm(1.6)
            texto_rico(p, m.group(2)); p.paragraph_format.space_after = Pt(2)
            i += 1; continue
        m = re.match(r"^\s*(\d+)\.\s+(.*)", l)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.9); p.paragraph_format.first_line_indent = Cm(-0.6)
            p.paragraph_format.space_after = Pt(2)
            texto_rico(p, f"{m.group(1)}. " + m.group(2))
            i += 1; continue
        if s.startswith(">"):
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(0.8)
            texto_rico(p, s.lstrip("> "), color=GRIS)
            i += 1; continue
        if not s:
            i += 1; continue
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        texto_rico(p, s)
        i += 1
    doc.core_properties.title = titulo
    doc.core_properties.author = "Equipo del proyecto integrador PEU-CD"
    doc.save(salida)


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[1]
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else raiz / "INFORME_FINAL_PROYECTO_INTEGRADOR.md"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else raiz / "INFORME_FINAL_PROYECTO_INTEGRADOR.docx"
    convertir(entrada.read_text(encoding="utf-8"), salida)
    print(f"Escrito {salida} ({salida.stat().st_size // 1024} KB)")
