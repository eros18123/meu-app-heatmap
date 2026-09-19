import traceback

import flet as ft

VERDE = "#2ecc71"
AMARELO = "#f1c40f"
VERMELHO = "#e74c3c"
AZUL = "#3498db"
VAZIO = "#2A2A2A"
CAIXA = "#1C1C1C"
BRANCO = "#FFFFFF"
CINZA = "#B0B0B0"
CINZA_ESC = "#8A8A8A"

PASTAS_BUSCA = ["/storage/emulated/0", "/sdcard", "/storage"]


def main(page: ft.Page):
    page.title = "Anki Heatmap"
    page.bgcolor = "#121212"
    page.padding = 16
    page.scroll = "auto"

    estado = {"db": None}

    def limpar():
        page.controls.clear()

    def erro(msg, detalhe=""):
        limpar()
        page.add(
            ft.Text("ERRO", size=22, color=VERMELHO),
            ft.Text(str(msg), size=15, color=BRANCO),
            ft.Container(height=8),
            ft.Text(str(detalhe), size=10, color=CINZA, selectable=True),
            ft.Container(height=16),
            ft.ElevatedButton("Voltar", on_click=lambda _: tela_inicial()),
        )
        page.update()

    def preparar_banco(caminho_original):
        """Recebe o caminho escolhido pelo usuario e devolve o caminho de um
        arquivo sqlite pronto pra ler. Se o arquivo for um backup moderno
        (.colpkg/.apkg), que na verdade e um .zip, extrai o banco de dentro."""
        import os
        import shutil
        import tempfile
        import zipfile

        temp_dir = tempfile.gettempdir()
        copia = os.path.join(temp_dir, "anki_original_tmp")
        shutil.copy2(caminho_original, copia)

        if not zipfile.is_zipfile(copia):
            # Arquivo .anki2 puro, sem compactacao.
            destino = os.path.join(temp_dir, "anki_db_tmp.anki2")
            shutil.copy2(copia, destino)
            return destino

        with zipfile.ZipFile(copia, "r") as z:
            nomes = z.namelist()
            candidatos = ["collection.anki21", "collection.anki2"]
            escolhido = None
            for nome in candidatos:
                if nome in nomes:
                    escolhido = nome
                    break

            if escolhido is None:
                # So encontramos o formato zstd-compactado (collection.anki21b),
                # que este app ainda nao sabe descompactar.
                raise RuntimeError(
                    "Este backup (.colpkg/.apkg) usa um formato de "
                    "compactacao (zstd) que este app ainda nao suporta.\n\n"
                    "Arquivos encontrados dentro do backup:\n"
                    + "\n".join(nomes[:15])
                    + "\n\nTente gerar o backup como 'Exportar colecao' "
                    "(nao 'Criar backup'), ou use um collection.anki2 antigo."
                )

            destino = os.path.join(temp_dir, "anki_db_tmp.anki2")
            with z.open(escolhido) as origem, open(destino, "wb") as saida:
                shutil.copyfileobj(origem, saida)
            return destino

    def ano_atual():
        import datetime
        return datetime.datetime.now().year

    def ano_mais_recente(caminho_db):
        """Descobre o ano da ultima revisao no arquivo, para nao abrir
        num ano vazio quando o backup e antigo (ex: arquivo de 2023)."""
        import datetime
        import sqlite3

        try:
            db = preparar_banco(caminho_db)
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute("SELECT max(id) FROM revlog")
            max_id = cur.fetchone()[0]
            conn.close()
            if max_id:
                return datetime.datetime.fromtimestamp(max_id / 1000).year
        except Exception:
            pass
        return ano_atual()

    def gerar_heatmap(caminho_db, year):
        import datetime
        import sqlite3
        import time

        try:
            limpar()
            page.add(
                ft.Text(f"Lendo dados de {year}...", size=16, color=BRANCO),
                ft.ProgressRing(color=VERDE),
            )
            page.update()

            db = preparar_banco(caminho_db)

            inicio = datetime.date(year, 1, 1)
            fim = datetime.date(year, 12, 31)
            dias = (fim - inicio).days + 1
            ini_ts = int(time.mktime(inicio.timetuple()) * 1000)
            fim_ts = int(time.mktime((fim + datetime.timedelta(days=1)).timetuple()) * 1000)

            dados = {}
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute(
                "SELECT strftime('%Y-%m-%d', id/1000.0, 'unixepoch', 'localtime'),"
                " type, count() FROM revlog WHERE id >= ? AND id < ? GROUP BY 1, 2",
                (ini_ts, fim_ts),
            )
            for d_str, tipo, qtd in cur.fetchall():
                if d_str not in dados:
                    dados[d_str] = {"0": 0, "1": 0, "2": 0, "3": 0, "total": 0}
                t = str(tipo) if str(tipo) in ("0", "1", "2", "3") else "3"
                dados[d_str][t] += qtd
                dados[d_str]["total"] += qtd
            conn.close()

            maximo = max([d["total"] for d in dados.values()]) if dados else 1
            maximo = max(1, maximo)
            cores = {"0": VERDE, "1": AMARELO, "2": VERMELHO, "3": AZUL}

            linha = ft.Row(scroll="always", spacing=4)
            col = ft.Column(spacing=4)

            for _ in range((inicio.weekday() + 1) % 7):
                col.controls.append(ft.Container(width=13, height=13))

            for i in range(dias):
                d = inicio + datetime.timedelta(days=i)
                s = d.strftime("%Y-%m-%d")
                if s in dados:
                    dia = dados[s]
                    dom = max(("0", "1", "2", "3"), key=lambda k: dia[k])
                    q = ft.Container(
                        width=13, height=13, border_radius=2,
                        bgcolor=cores[dom],
                        opacity=max(0.3, min(1.0, dia["total"] / maximo)),
                        tooltip=f"{s}  total {dia['total']}",
                    )
                else:
                    q = ft.Container(width=13, height=13, border_radius=2, bgcolor=VAZIO)
                col.controls.append(q)
                if len(col.controls) == 7:
                    linha.controls.append(col)
                    col = ft.Column(spacing=4)
            if col.controls:
                linha.controls.append(col)

            total = sum(d["total"] for d in dados.values()) if dados else 0

            limpar()
            controles_topo = [
                ft.Text(f"Heatmap {year}", size=24, color=BRANCO),
                ft.Text(f"{total} revisoes", size=13, color=CINZA),
            ]
            if total == 0:
                controles_topo.append(
                    ft.Text(
                        "Nenhuma revisao neste ano. Use os botoes abaixo\n"
                        "para navegar ate um ano com dados.",
                        size=11, color=AMARELO,
                    )
                )
            page.add(
                *controles_topo,
                ft.Container(height=10),
                ft.Row(
                    [
                        ft.ElevatedButton("< " + str(year - 1),
                                          on_click=lambda _: gerar_heatmap(caminho_db, year - 1)),
                        ft.ElevatedButton(str(year + 1) + " >",
                                          on_click=lambda _: gerar_heatmap(caminho_db, year + 1)),
                    ],
                    alignment="center",
                ),
                ft.Container(height=14),
                ft.Container(content=linha, padding=10, bgcolor=CAIXA, border_radius=10),
                ft.Container(height=14),
                ft.Row(
                    [
                        ft.Text("verde novo", size=10, color=VERDE),
                        ft.Text("amarelo mad", size=10, color=AMARELO),
                        ft.Text("vermelho apr", size=10, color=VERMELHO),
                        ft.Text("azul filt", size=10, color=AZUL),
                    ],
                    wrap=True, spacing=10,
                ),
                ft.Container(height=14),
                ft.ElevatedButton("Inicio", on_click=lambda _: tela_inicial()),
            )
            page.update()

        except Exception:
            erro("Nao foi possivel gerar o heatmap", traceback.format_exc())

    # ---------- file picker ----------
    def on_pick(e):
        try:
            if getattr(e, "files", None):
                caminho = e.files[0].path
                if caminho:
                    estado["db"] = caminho
                    gerar_heatmap(caminho, ano_mais_recente(caminho))
                else:
                    erro("Caminho vazio", "O picker nao retornou um caminho valido.")
        except Exception:
            erro("Falha ao abrir o arquivo", traceback.format_exc())

    picker = ft.FilePicker(on_result=on_pick)
    try:
        if hasattr(page, "services"):
            page.services.append(picker)
        else:
            page.overlay.append(picker)
    except Exception:
        pass

    # ---------- busca automatica ----------
    def procurar_arquivos(e=None):
        import os

        limpar()
        page.add(
            ft.Text("Procurando arquivos .anki2...", size=16, color=BRANCO),
            ft.ProgressRing(color=VERDE),
        )
        page.update()

        encontrados = []
        visitados = 0
        try:
            for raiz in PASTAS_BUSCA:
                if not os.path.isdir(raiz):
                    continue
                base_depth = raiz.rstrip("/").count("/")
                for dirpath, dirnames, filenames in os.walk(raiz, topdown=True):
                    visitados += 1
                    if visitados > 8000 or len(encontrados) >= 25:
                        break
                    if dirpath.count("/") - base_depth > 6:
                        dirnames[:] = []
                        continue
                    dirnames[:] = [
                        d for d in dirnames
                        if not d.startswith(".")
                        and d not in ("Android_old", "LOST.DIR", "node_modules")
                    ]
                    for nome in filenames:
                        if nome.endswith(".anki2"):
                            caminho = os.path.join(dirpath, nome)
                            if caminho not in encontrados:
                                encontrados.append(caminho)
                if len(encontrados) >= 25:
                    break
        except Exception:
            pass

        limpar()
        if not encontrados:
            page.add(
                ft.Text("Nenhum .anki2 encontrado automaticamente", size=18, color=BRANCO),
                ft.Container(height=8),
                ft.Text(
                    "O Android costuma bloquear a leitura de /Android/data.\n"
                    "Use 'Selecionar manualmente' abaixo.",
                    size=12, color=CINZA,
                ),
                ft.Container(height=16),
                ft.ElevatedButton("Voltar", on_click=lambda _: tela_inicial()),
            )
            page.update()
            return

        itens = [
            ft.Text(f"{len(encontrados)} arquivo(s) encontrado(s)", size=18, color=BRANCO),
            ft.Container(height=10),
        ]
        for caminho in encontrados:
            def usar(_e, c=caminho):
                estado["db"] = c
                gerar_heatmap(c, ano_mais_recente(c))

            itens.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(caminho, size=11, color=CINZA, selectable=True),
                            ft.ElevatedButton("Usar este", on_click=usar),
                        ],
                        spacing=6,
                    ),
                    bgcolor=CAIXA,
                    padding=10,
                    border_radius=8,
                )
            )
            itens.append(ft.Container(height=8))

        itens.append(ft.ElevatedButton("Voltar", on_click=lambda _: tela_inicial()))
        page.add(*itens)
        page.update()

    def tela_inicial(e=None):
        limpar()
        page.add(
            ft.Container(height=20),
            ft.Text("Anki Heatmap", size=28, color=BRANCO),
            ft.Container(height=6),
            ft.Text("Carregue o seu collection.anki2", size=13, color=CINZA),
            ft.Container(height=24),
            ft.ElevatedButton("Procurar arquivo .anki2", on_click=procurar_arquivos,
                              width=280, height=48),
            ft.Container(height=10),
            ft.ElevatedButton("Selecionar manualmente",
                              on_click=lambda _: picker.pick_files(),
                              width=280, height=48,
                              bgcolor=AZUL, color=BRANCO),
            ft.Container(height=20),
            ft.Text(
                "Dica: se a busca automatica nao achar nada,\n"
                "use 'Selecionar manualmente'.",
                size=11, color=CINZA_ESC,
            ),
        )
        page.update()

    tela_inicial()


ft.app(target=main)
