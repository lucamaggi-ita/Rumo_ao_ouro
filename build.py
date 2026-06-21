#!/usr/bin/env python3
"""
build.py — Gerador do site HTML "Rumo ao Ouro"

Uso:
    pip install markdown
    python build.py

Saída: pasta  site/  (abrir site/index.html no navegador)
"""

import re
import sys
import json
import shutil
import zipfile
import html as _html
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("Erro: instale com   pip install markdown")

# ─── Caminhos ─────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent
SITE    = ROOT / "site"
ASSETS  = ROOT / "assets"
ZIP_FIG = ROOT / "RUMO_AO_OURO_CAP45_FIGURAS_FINAIS.zip"

# ─── Mapeamento de capítulos ───────────────────────────────────────────────────
# (número de produção, número final no livro)
CAPS = [(p, p - 18) for p in range(19, 36)]

NIVEL = {
    **{n: ("bronze", "Nível Bronze") for n in range(1,  10)},
    **{n: ("prata",  "Nível Prata")  for n in range(10, 16)},
    **{n: ("ouro",   "Nível Ouro")   for n in range(16, 18)},
}

# Coletores globais
TOOLS: dict        = {}   # {num: {desc, chapter}}
OFICINAS: list     = []   # [{title, chapter}]
CAP_TITLES: dict   = {}   # {final_num: title}
SVG_MANIFEST: dict = {}   # {final_num: [filename, ...]}  (em ordem)
SVG_COUNTERS: dict = {}   # {final_num: index}  (incrementado ao usar)

# ─── SVG ──────────────────────────────────────────────────────────────────────
def load_svg_manifest():
    """Lê o MANIFESTO_SVG.json do ZIP e monta {final_num: [svg_file, ...]}."""
    global SVG_MANIFEST
    if not ZIP_FIG.exists():
        return
    with zipfile.ZipFile(ZIP_FIG) as z:
        with z.open("rumo_ao_ouro_figuras_finais/MANIFESTO_SVG.json") as f:
            entries = json.load(f)
    by_chapter: dict = {}
    for e in entries:
        prod = int(e["chapter"])
        final = prod - 18
        by_chapter.setdefault(final, []).append(e["file"])
    # Garantir ordem correta por número de figura (F01, F02, ...)
    def fig_order(fname):
        m = re.search(r"_F(\d+)_", fname)
        return int(m.group(1)) if m else 0
    for final_num in by_chapter:
        by_chapter[final_num].sort(key=fig_order)
    SVG_MANIFEST = by_chapter

def extract_svgs() -> int:
    """Extrai todas as SVG do ZIP para site/assets/figuras/."""
    dest = SITE / "assets" / "figuras"
    dest.mkdir(parents=True, exist_ok=True)
    if not ZIP_FIG.exists():
        return 0
    count = 0
    with zipfile.ZipFile(ZIP_FIG) as z:
        for name in z.namelist():
            if name.endswith(".svg"):
                filename = Path(name).name
                (dest / filename).write_bytes(z.read(name))
                count += 1
    return count

# ─── Normalização de títulos ──────────────────────────────────────────────────
def normalize_title(title: str) -> str:
    """Converte títulos EM MAIÚSCULAS para título normal (sentence case)."""
    alpha = [c for c in title if c.isalpha()]
    if not alpha:
        return title
    upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
    if upper_ratio < 0.65:
        return title  # Já está em caixa normal
    lower = title.lower()
    return lower[0].upper() + lower[1:]

# ─── Pré-processamento do markdown ────────────────────────────────────────────
def strip_header(raw: str) -> tuple:
    """
    Retorna (título, corpo) removendo o cabeçalho editorial.
    Mantém o H1 e começa o conteúdo após o primeiro '---'.
    """
    lines = raw.split("\n")
    title = ""
    for i, line in enumerate(lines):
        if not title and line.startswith("#"):
            m = re.match(
                r"^#{1,2}\s+CAP[ÍI]TULO\s+\d+\s*[—–\-]\s*(.+)$",
                line, re.IGNORECASE
            )
            if m:
                raw_title = m.group(1).strip()
            else:
                # Fallback: remove qualquer prefixo "Capitulo N - " ou similar
                raw = line.lstrip("#").strip()
                raw_title = re.sub(r"^Cap[ií]tulo\s+\d+\s*[-—–]\s*", "", raw, flags=re.IGNORECASE)
            title = normalize_title(raw_title)
        if line.strip() == "---":
            body = "\n".join(lines[i + 1:])
            # Remove linhas com metadados editoriais restantes logo no início
            body_lines = body.split("\n")
            clean = []
            skip_meta = True
            for bl in body_lines:
                if skip_meta and re.match(r"^\*\*(Versão|Função|Observação|Nota de auditoria|Projeto|Academia do Raciocínio)", bl):
                    continue
                elif skip_meta and bl.strip() in ("---", ""):
                    continue
                else:
                    skip_meta = False
                    clean.append(bl)
            return title, "\n".join(clean)
    return title, raw

def collect_tools(text: str, final_num: int) -> str:
    """Encontra Ferramentas, registra e substitui por bloco HTML."""
    pat = re.compile(
        r"^\s*>\s*\*\*(?:Ferramenta|Ferramenta da Mochila)\s+(\d+)\s*[—–\-]\s*(.+?)\*\*\.?\s*$",
        re.MULTILINE,
    )
    def repl(m):
        num  = int(m.group(1))
        desc = m.group(2).strip().rstrip(".")
        if num not in TOOLS:
            TOOLS[num] = {"desc": desc, "chapter": final_num}
        esc = _html.escape(desc)
        return (
            f'\n\n<div class="ferramenta" data-num="{num}" id="f{num}">'
            f'<span class="f-badge">Ferramenta {num}</span>'
            f'<span class="f-text">{esc}</span>'
            f'</div>\n\n'
        )
    return pat.sub(repl, text)

def collect_oficinas(text: str, final_num: int) -> None:
    """Registra seções de Oficina."""
    for m in re.finditer(
        r"^#{1,3}\s+(\d+\.\s+Oficina[^\n]+)",
        text, re.MULTILINE
    ):
        OFICINAS.append({"title": m.group(1).strip(), "chapter": final_num})

def replace_figuras(text: str, final_num: int) -> str:
    """
    Substitui specs de figura por <figure><img> (criar/adaptar)
    ou por div estilizado (manter).
    """
    pat = re.compile(
        r"^\s*>\s*\*\*Especificação de figura\s*[—–\-]\s*(criar|adaptar|manter|dispensar)\.\s*\*\*\s*(.*)$",
        re.MULTILINE,
    )
    def repl(m):
        tipo = m.group(1)
        desc = m.group(2).strip()
        esc  = _html.escape(desc)

        if tipo == "manter":
            return (
                f'\n\n<div class="figura-spec fig-manter">'
                f'<span class="fig-label">Tabela</span>'
                f'<span class="fig-desc">{esc}</span>'
                f'</div>\n\n'
            )
        if tipo == "dispensar":
            return ""

        # criar ou adaptar: usar próxima SVG do capítulo
        chapter_svgs = SVG_MANIFEST.get(final_num, [])
        idx = SVG_COUNTERS.get(final_num, 0)
        if idx < len(chapter_svgs):
            svg_file = chapter_svgs[idx]
            SVG_COUNTERS[final_num] = idx + 1
            return (
                f'\n\n<figure class="figura">'
                f'<img src="../assets/figuras/{svg_file}" alt="{esc}" loading="lazy">'
                f'<figcaption>{esc}</figcaption>'
                f'</figure>\n\n'
            )
        else:
            return (
                f'\n\n<div class="figura-spec fig-{tipo}">'
                f'<span class="fig-label">figura — {tipo}</span>'
                f'<span class="fig-desc">{esc}</span>'
                f'</div>\n\n'
            )
    return pat.sub(repl, text)

def replace_frase_academia(text: str) -> str:
    """Marca o cabeçalho '> **Frase da Academia**' com classe especial."""
    return re.sub(
        r"^\s*>\s*\*\*Frase da Academia\*\*\s*$",
        '\n\n<p class="frase-label">Frase da Academia</p>\n\n',
        text,
        flags=re.MULTILINE,
    )

def mark_solution_sections(text: str) -> str:
    """
    Envolve seções 'Solução' em comentários HTML especiais,
    que serão convertidos em <details> após a conversão markdown.
    Trabalha linha a linha para respeitar hierarquia.
    """
    lines  = text.split("\n")
    out    = []
    in_sol = False
    sol_lv = 0

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            lv    = len(m.group(1))
            title = m.group(2)
            if in_sol and lv <= sol_lv:
                out.append("<!-- /SOLUCAO -->")
                in_sol = False
            if re.search(r"Solu[çc][aã]o", title, re.IGNORECASE):
                out.append("<!-- SOLUCAO -->")
                in_sol, sol_lv = True, lv
        out.append(line)

    if in_sol:
        out.append("<!-- /SOLUCAO -->")

    return "\n".join(out)

# ─── Pós-processamento do HTML ─────────────────────────────────────────────────
def post_process(html: str) -> str:
    """Converte marcadores em elementos HTML especiais."""

    # Wrapping de soluções em <details>
    html = re.sub(
        r"<!-- SOLUCAO -->(.*?)<!-- /SOLUCAO -->",
        (
            '<details class="solucao">'
            '<summary>Ver solução</summary>'
            '<div class="sol-body">\\1</div>'
            '</details>'
        ),
        html,
        flags=re.DOTALL,
    )

    # Badge nas seções de Problema em estilo OBMEP
    html = re.sub(
        r"(<h2[^>]*>)(\d+\.\s+Problema em estilo OBMEP\s*[—–\-]\s*)",
        r'\1<span class="badge-obmep">OBMEP</span>\2',
        html,
    )

    # Badge nas seções de Oficina
    html = re.sub(
        r"(<h2[^>]*>)(\d+\.\s+Oficina[^<]*)(</h2>)",
        r'\1<span class="badge-oficina">Oficina</span>\2\3',
        html,
    )

    return html

# ─── Conversão markdown → HTML ─────────────────────────────────────────────────
def md_to_html(text: str) -> str:
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code"],
        output_format="html",
    )

# ─── Template de página de capítulo ───────────────────────────────────────────
def build_sidebar(current: int) -> str:
    """Gera o HTML da sidebar de navegação com todos os capítulos."""
    links = []
    prev_nivel = None
    for prod, final in CAPS:
        cap_title = CAP_TITLES.get(final, f"Capítulo {final}")
        nivel_cls = NIVEL[final][0]
        active = ' sidebar-active' if final == current else ''
        # Separator between level groups
        if nivel_cls != prev_nivel:
            label = {"bronze": "Bronze", "prata": "Prata", "ouro": "Ouro"}[nivel_cls]
            links.append(f'<div class="s-level-label nivel-{nivel_cls}">{label}</div>')
            prev_nivel = nivel_cls
        links.append(
            f'<a href="cap{final:02d}.html" class="sidebar-link{active}" '
            f'title="{_html.escape(cap_title)}">'
            f'<span class="s-num">{final}</span>'
            f'<span class="s-title">{_html.escape(cap_title)}</span>'
            f'</a>'
        )
    return "\n".join(links)

def chapter_page(title: str, nivel_cls: str, nivel_name: str,
                 content: str, final_num: int) -> str:
    prev_lnk = (
        f'<a href="cap{final_num-1:02d}.html" class="nav-prev">'
        f'← Cap. {final_num-1}</a>'
    ) if final_num > 1 else '<span></span>'
    next_lnk = (
        f'<a href="cap{final_num+1:02d}.html" class="nav-next">'
        f'Cap. {final_num+1} →</a>'
    ) if final_num < 17 else '<span></span>'

    sidebar_html = build_sidebar(final_num)

    return f"""<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cap. {final_num} — {_html.escape(title)} | Rumo ao Ouro</title>
<link rel="stylesheet" href="../assets/css/style.css">
<script>
MathJax = {{
  tex: {{
    inlineMath: [["\\\\(","\\\\)"]],
    displayMath: [["\\\\[","\\\\]"]]
  }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>
</head>
<body>

<header class="site-header">
  <div class="header-left">
    <button class="btn-icon btn-menu" id="btn-menu" onclick="toggleSidebar()" title="Menu capítulos">
      ☰
    </button>
    <a href="../index.html" class="logo-link">Rumo ao Ouro</a>
    <span class="nivel-badge nivel-{nivel_cls}">{nivel_name}</span>
  </div>
  <div class="header-right">
    <button class="btn-icon" id="btn-treino" onclick="toggleTreino()" title="Modo Treino">
      ✏ Treino
    </button>
    <button class="btn-icon" id="btn-mochila" onclick="toggleMochila()" title="Mochila do Matemático">
      🎒 Mochila
    </button>
    <button class="btn-icon" id="btn-theme" onclick="toggleTheme()" title="Tema claro/escuro">
      🌙
    </button>
  </div>
</header>

<aside id="mochila-panel" class="mochila-panel" aria-hidden="true">
  <div class="mochila-header">
    <span>🎒 Mochila do Matemático</span>
    <button onclick="toggleMochila()" class="btn-close">✕</button>
  </div>
  <input type="search" id="mochila-search" placeholder="Buscar ferramenta..."
         oninput="filterMochila(this.value)">
  <div id="mochila-list" class="mochila-list"></div>
</aside>
<div id="mochila-overlay" class="mochila-overlay" onclick="toggleMochila()"></div>

<div class="page-layout">

  <nav class="sidebar" id="sidebar" aria-label="Capítulos">
    <div class="sidebar-top">
      <a href="../index.html" class="sidebar-home">← Índice geral</a>
    </div>
{sidebar_html}
    <div class="sidebar-links">
      <a href="../mochila.html" class="sidebar-extra">🎒 Mochila</a>
      <a href="../oficinas.html" class="sidebar-extra">⚙ Oficinas</a>
    </div>
  </nav>
  <div id="sidebar-overlay" class="sidebar-overlay" onclick="toggleSidebar()"></div>

  <div class="page-content">
    <main class="chapter">
      <div class="chapter-title-block">
        <span class="cap-label">Capítulo {final_num}</span>
        <h1 class="cap-title">{_html.escape(title)}</h1>
      </div>
      <article class="chapter-body">
{content}
      </article>
    </main>

    <nav class="chapter-nav">
      {prev_lnk}
      {next_lnk}
    </nav>
  </div>

</div>

<script src="../assets/js/mochila-data.js"></script>
<script src="../assets/js/app.js"></script>
<script>initChapter({final_num});</script>
</body>
</html>"""

# ─── Processamento de capítulos ────────────────────────────────────────────────
def build_chapter(prod: int, final: int) -> tuple:
    """Processa um capítulo e retorna (título, html_content)."""
    src = ROOT / f"CAPITULO_{prod}_RUMO_AO_OURO_CAP41_FIGURAS_APLICADAS.md"
    if not src.exists():
        return f"Capítulo {final}", f"<p>Arquivo não encontrado: {src.name}</p>"

    raw = src.read_text(encoding="utf-8")
    title, body = strip_header(raw)
    CAP_TITLES[final] = title

    collect_oficinas(body, final)

    body = collect_tools(body, final)
    body = replace_figuras(body, final)
    body = replace_frase_academia(body)
    body = mark_solution_sections(body)

    html_content = md_to_html(body)
    html_content = post_process(html_content)

    return title, html_content

# ─── Páginas estáticas ─────────────────────────────────────────────────────────
def build_index() -> str:
    items = []
    for prod, final in CAPS:
        title      = CAP_TITLES.get(final, f"Capítulo {final}")
        nivel_cls, nivel_name = NIVEL[final]
        items.append(
            f'<li class="idx-item nivel-{nivel_cls}" data-cap="{final}" id="idx-{final}">'
            f'  <a href="capitulos/cap{final:02d}.html">'
            f'    <span class="idx-num">{final}</span>'
            f'    <span class="idx-title">{_html.escape(title)}</span>'
            f'  </a>'
            f'  <span class="idx-nivel">{nivel_name}</span>'
            f'  <span class="idx-status" id="status-{final}"></span>'
            f'</li>'
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rumo ao Ouro</title>
<link rel="stylesheet" href="assets/css/style.css">
</head>
<body>

<header class="site-header home-header">
  <div class="header-left">
    <span class="logo">Rumo ao Ouro</span>
  </div>
  <div class="header-right">
    <a href="mochila.html" class="btn-icon">🎒 Mochila</a>
    <a href="oficinas.html" class="btn-icon">⚙ Oficinas</a>
    <button class="btn-icon" id="btn-theme" onclick="toggleTheme()">🌙</button>
  </div>
</header>

<main class="home">
  <div class="home-hero">
    <h1>Rumo ao Ouro</h1>
    <p class="home-subtitle">Preparação para a Segunda Fase da OBMEP — Nível 2</p>
    <div class="legend">
      <span class="nivel-badge nivel-bronze">Nível Bronze (caps. 1–9)</span>
      <span class="nivel-badge nivel-prata">Nível Prata (caps. 10–15)</span>
      <span class="nivel-badge nivel-ouro">Nível Ouro (caps. 16–17)</span>
    </div>
  </div>
  <ol class="chapter-list">
    {''.join(items)}
  </ol>
</main>

<script src="assets/js/app.js"></script>
<script>initIndex();</script>
</body>
</html>"""

def build_mochila_page() -> str:
    # Agrupa ferramentas por capítulo
    by_cap: dict = {}
    for num in sorted(TOOLS):
        cap = TOOLS[num]["chapter"]
        by_cap.setdefault(cap, []).append((num, TOOLS[num]["desc"]))

    sections = []
    for cap in sorted(by_cap):
        title     = CAP_TITLES.get(cap, f"Capítulo {cap}")
        nivel_cls = NIVEL.get(cap, ("bronze", ""))[0]
        items_html = "".join(
            f'<li class="tool-item" data-num="{n}">'
            f'  <a href="capitulos/cap{cap:02d}.html#f{n}">'
            f'    <span class="t-num">{n}</span>'
            f'    <span class="t-desc">{_html.escape(d)}</span>'
            f'  </a>'
            f'</li>'
            for n, d in by_cap[cap]
        )
        sections.append(
            f'<section class="mochila-sec nivel-{nivel_cls}">'
            f'<h2><a href="capitulos/cap{cap:02d}.html">Capítulo {cap} — {_html.escape(title)}</a></h2>'
            f'<ul class="tool-list">{items_html}</ul>'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mochila do Matemático | Rumo ao Ouro</title>
<link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
<header class="site-header">
  <div class="header-left">
    <a href="index.html" class="logo-link">← Rumo ao Ouro</a>
  </div>
  <div class="header-right">
    <input type="search" id="tool-search" placeholder="Buscar ferramenta…"
           oninput="filterTools(this.value)">
    <button class="btn-icon" id="btn-theme" onclick="toggleTheme()">🌙</button>
  </div>
</header>
<main class="mochila-page">
  <h1>🎒 Mochila do Matemático</h1>
  <p class="page-intro">{len(TOOLS)} ferramentas — organizadas por capítulo, com link ao ponto de introdução.</p>
  {''.join(sections)}
</main>
<script src="assets/js/app.js"></script>
<script>initMochilaPage();</script>
</body>
</html>"""

def build_oficinas_page() -> str:
    items_html = []
    for of in OFICINAS:
        cap       = of["chapter"]
        nivel_cls = NIVEL.get(cap, ("bronze", ""))[0]
        items_html.append(
            f'<li class="of-item nivel-{nivel_cls}">'
            f'  <a href="capitulos/cap{cap:02d}.html">{_html.escape(of["title"])}</a>'
            f'  <span class="of-cap">Cap. {cap}</span>'
            f'</li>'
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oficinas Olímpicas | Rumo ao Ouro</title>
<link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
<header class="site-header">
  <div class="header-left">
    <a href="index.html" class="logo-link">← Rumo ao Ouro</a>
  </div>
  <div class="header-right">
    <button class="btn-icon" id="btn-theme" onclick="toggleTheme()">🌙</button>
  </div>
</header>
<main class="oficinas-page">
  <h1>⚙ Oficinas Olímpicas</h1>
  <p class="page-intro">{len(OFICINAS)} oficinas — exercícios de preparação ao final de cada fase.</p>
  <ul class="of-list">
    {''.join(items_html)}
  </ul>
</main>
<script src="assets/js/app.js"></script>
</body>
</html>"""

def build_mochila_data_js() -> str:
    """Gera JS com os dados completos da Mochila."""
    data = {str(k): v for k, v in sorted(TOOLS.items())}
    return f"const MOCHILA_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};\n"

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=== Rumo ao Ouro - construindo site ===\n")

    # Criar estrutura de saída
    cap_dir = SITE / "capitulos"
    cap_dir.mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "js").mkdir(parents=True, exist_ok=True)

    # Carregar manifesto de SVGs
    load_svg_manifest()
    cap_count = sum(len(v) for v in SVG_MANIFEST.values())
    print(f"  Manifesto SVG: {cap_count} figuras indexadas")

    # Extrair SVGs do ZIP
    n_svg = extract_svgs()
    print(f"  SVGs extraidas para site/assets/figuras/: {n_svg}\n")

    # Processar capítulos
    chapters_data = {}
    for prod, final in CAPS:
        title, content = build_chapter(prod, final)
        chapters_data[final] = (title, content)
        tool_count = sum(1 for t in TOOLS.values() if t["chapter"] == final)
        title_ascii = title.encode("ascii", "replace").decode("ascii")
        print(f"  [OK] Cap. {final:02d} - {title_ascii}  [{tool_count} ferramentas]")

    # Escrever HTML dos capítulos
    print()
    for prod, final in CAPS:
        title, content = chapters_data[final]
        nivel_cls, nivel_name = NIVEL[final]
        page_html = chapter_page(title, nivel_cls, nivel_name, content, final)
        (cap_dir / f"cap{final:02d}.html").write_text(page_html, encoding="utf-8")

    # Escrever páginas principais
    (SITE / "index.html").write_text(build_index(), encoding="utf-8")
    (SITE / "mochila.html").write_text(build_mochila_page(), encoding="utf-8")
    (SITE / "oficinas.html").write_text(build_oficinas_page(), encoding="utf-8")

    # Escrever dados da Mochila em JS
    js_data = build_mochila_data_js()
    (SITE / "assets" / "js" / "mochila-data.js").write_text(js_data, encoding="utf-8")

    # Copiar assets estáticos
    css_src = ASSETS / "css" / "style.css"
    js_src  = ASSETS / "js"  / "app.js"
    if css_src.exists():
        shutil.copy(css_src, SITE / "assets" / "css" / "style.css")
        print("  [OK] style.css copiato")
    else:
        print("  [!] assets/css/style.css non trovato")
    if js_src.exists():
        shutil.copy(js_src, SITE / "assets" / "js" / "app.js")
        print("  [OK] app.js copiato")
    else:
        print("  [!] assets/js/app.js non trovato")

    # Resumo
    print(f"""
SITE GERADO: {SITE}

  Ferramentas indexadas : {len(TOOLS)}
  Oficinas indexadas    : {len(OFICINAS)}
  SVGs usadas           : {sum(SVG_COUNTERS.values())}

  Abrir: {SITE / 'index.html'}
""")

if __name__ == "__main__":
    main()
