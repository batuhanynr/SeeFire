#!/usr/bin/env python3
"""
SeeFire Sunum PDF'i Oluşturucu (HTML ile)
============================================
presentation.md dosyasını HTML'e çevirip PDF sunumu oluşturur.
"""

import re

try:
    from weasyprint import HTML, CSS
except ImportError:
    print("WeasyPrint kurulu değil. Kuruluyor...")
    import subprocess
    subprocess.run(['pip3', 'install', 'weasyprint'], check=True)
    from weasyprint import HTML, CSS

def parse_markdown_to_slides(md_content):
    """Markdown içeriğini slaytlara ayır."""
    lines = md_content.split('\n')
    slides = []
    current_slide = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if line.strip() == '---':
            if current_slide:
                slides.append('\n'.join(current_slide))
                current_slide = []
            continue

        current_slide.append(line)

    if current_slide:
        slides.append('\n'.join(current_slide))

    return slides

def markdown_to_html(slides):
    """Markdown slaytlarını HTML'e çevir."""
    html_slides = []

    for i, slide in enumerate(slides):
        lines = slide.split('\n')
        html_content = []
        in_list = False

        for line in lines:
            if not line.strip():
                continue

            # Başlıklar
            if line.startswith('# '):
                text = line[2:].strip()
                if i == 0:  # İlk slayt → kapak
                    html_content.append(f'<h1 class="cover-title">{text}</h1>')
                else:
                    html_content.append(f'<h1>{text}</h1>')
            elif line.startswith('## '):
                text = line[3:].strip()
                html_content.append(f'<h2 class="slide-title">{text}</h2>')
            elif line.startswith('### '):
                text = line[4:].strip()
                html_content.append(f'<h3 class="slide-subtitle">{text}</h3>')
            # Liste maddeleri
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                if not in_list:
                    html_content.append('<ul class="bullet-list">')
                    in_list = True
                text = line.strip()[2:]
                html_content.append(f'<li>{text}</li>')
            # Numaralı liste
            elif re.match(r'^\d+\.\s', line.strip()):
                if not in_list:
                    html_content.append('<ul class="bullet-list">')
                    in_list = True
                text = re.sub(r'^\d+\.\s', '', line.strip())
                html_content.append(f'<li>{text}</li>')
            # Tablo satırı
            elif '|' in line and not line.strip().startswith('|--'):
                if not in_list:
                    html_content.append('<table class="info-table">')
                    in_list = True
                parts = [p.strip() for p in line.split('|') if p.strip()]
                row_html = '<tr>' + ''.join(f'<td>{p}</td>' for p in parts) + '</tr>'
                html_content.append(row_html)
            # Normal paragraf
            else:
                if in_list:
                    if 'table' in html_content[-1]:
                        html_content.append('</table>')
                    else:
                        html_content.append('</ul>')
                    in_list = False
                text = line.strip()
                # Kalın ve italik
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
                html_content.append(f'<p>{text}</p>')

        if in_list:
            if 'table' in html_content[-1] or 'table' in html_content[-2] if len(html_content) > 1 else False:
                html_content.append('</table>')
            else:
                html_content.append('</ul>')

        slide_html = '\n'.join(html_content)
        html_slides.append(slide_html)

    return html_slides

def create_html_with_css(html_slides):
    """HTML içeriğini CSS ile birleştir."""
    css = '''
    @page {
        size: A4 landscape;
        margin: 1cm;
    }

    body {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        margin: 0;
        padding: 0;
        color: #2d3748;
    }

    .slide {
        page-break-after: always;
        min-height: 100vh;
        padding: 2cm;
    }

    h1.cover-title {
        font-size: 48pt;
        color: #1a1a1a;
        text-align: center;
        margin-top: 30%;
        font-weight: bold;
    }

    h1 {
        font-size: 32pt;
        color: #2c5282;
        margin-top: 1cm;
        font-weight: bold;
    }

    h2.slide-title {
        font-size: 28pt;
        color: #2c5282;
        margin-top: 0.5cm;
        font-weight: bold;
    }

    h3.slide-subtitle {
        font-size: 18pt;
        color: #4a5568;
        margin-top: 0.3cm;
    }

    ul.bullet-list {
        list-style: none;
        padding-left: 0;
        margin-top: 0.5cm;
    }

    ul.bullet-list li {
        font-size: 14pt;
        margin-bottom: 0.3cm;
        padding-left: 0.5cm;
        position: relative;
    }

    ul.bullet-list li:before {
        content: "•";
        position: absolute;
        left: 0;
        color: #2c5282;
        font-weight: bold;
    }

    table.info-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.5cm;
    }

    table.info-table td {
        border: 1px solid #e2e8f0;
        padding: 0.3cm;
        font-size: 12pt;
    }

    p {
        font-size: 14pt;
        margin-bottom: 0.3cm;
        line-height: 1.4;
    }

    strong {
        font-weight: bold;
        color: #1a1a1a;
    }

    em {
        font-style: italic;
    }
    '''

    full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SeeFire Sunum</title>
    <style>{css}</style>
</head>
<body>
'''

    for slide_html in html_slides:
        full_html += f'<div class="slide">{slide_html}</div>\n'

    full_html += '</body></html>'
    return full_html

def create_pdf():
    """HTML'den PDF oluştur."""
    # Markdown dosyasını oku
    with open('presentation.md', 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Markdown'ı slaytlara ayır
    slides = parse_markdown_to_slides(md_content)

    # Slaytları HTML'e çevir
    html_slides = markdown_to_html(slides)

    # HTML ve CSS birleştir
    full_html = create_html_with_css(html_slides)

    # PDF'e çevir (WeasyPrint)
    output_file = "SeeFire_Sunum.pdf"

    print(f"PDF oluşturuluyor: {output_file}")
    HTML(string=full_html, base_url='.').write_pdf(output_file)
    print(f"✅ PDF hazır: {output_file}")

if __name__ == "__main__":
    create_pdf()
