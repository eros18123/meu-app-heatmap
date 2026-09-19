import traceback

import flet as ft

# Cores em hexadecimal puro. Nao usar ft.Colors: os nomes mudam entre versoes
# do Flet e um AttributeError aqui derruba o app inteiro na abertura.
BRANCO = "#FFFFFF"
CINZA = "#B0B0B0"
CINZA_ESC = "#8A8A8A"
VAZIO = "#2A2A2A"
FUNDO = "#121212"
CAIXA = "#1C1C1C"
VERDE = "#2ecc71"
AMARELO = "#f1c40f"
VERMELHO = "#e74c3c"
AZUL = "#3498db"

PASTAS_BUSCA = [
    "/storage/emulated/0",
    "/sdcard",
    "/storage",
]


def main(page: ft.Page):
    """Wrapper: qualquer erro vira texto na tela em vez de app fechando."""
    try:
        app(page)
    except Exception:
        try:
            page.controls.clear()
            page.add(
                ft.Text("ERRO NA INICIALIZACAO", size=18, color=VERMELHO),
                ft.Text(traceback.format_exc(), size=10, color=BRANCO, selectable=True),
            )
            page.update()
        except Exception:
            pass


def app(page: ft.Page):
    # ---------- configuracao da pagina (cada linha isolada) ----------
    for attr, valor in [
        ("title", "Anki Heatmap"),
        ("bgcolor", FUNDO),
        ("padding", 16),
    ]:
        try:
            setattr(page, attr, valor)
        except Exception:
            pass
    try:
        page.theme_mode = "dark"
    except Exception:
        pass
    try:
        page.scroll = "auto"
    except Exception:
        pass

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

    # ---------- file picker (opcional: se falhar, o app continua) ----------
    picker = None

    def on_pick(e):
        try:
            if getattr(e, "files", None):
                caminho = e.files[0].path
                if caminho:
                    estado["db"] = caminho
                    gerar_heatmap(caminho, ano_atual())
                else:
                    erro("O Android nao liberou o caminho real do arquivo.",
                         "Use o botao 'Procurar arquivo .anki2'.")
        except Exception:
            erro("Falha ao abrir o arquivo", traceback.format_exc())

    try:
        picker = ft.FilePicker(on_result=on_pick)
        if hasattr(page, "services"):
            page.services.append(picker)
        else:
            page.overlay.append(picker)
    except Exception:
        picker = None

    def ano_atual():
        import datetime
        return datetime.datetime.now().year

    # ---------- varredura do celular ----------
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
                    # nao entra em pastas de sistema/lixo nem muito fundo
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
                ft.Text("Nenhum .anki2 encontrado", size=20, color=BRANCO),
                ft.Container(height=8),
                ft.Text(
                    "O Android costuma bloquear a leitura de /Android/data.\n"
                    "Tente o botao 'Selecionar manualmente' ou copie o\n"
                    "collection.anki2 para a pasta Download do celular.",
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
                gerar_heatmap(c, ano_atual())

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

    # ---------- heatmap ----------
    def gerar_heatmap(caminho_db, year):
        import datetime
        import os
        import sqlite3
        import time

        try:
            limpar()
            page.add(
                ft.Text(f"Lendo dados de {year}...", size=16, color=BRANCO),
                ft.ProgressRing(color=VERDE),
            )
            page.update()

            # copia para pasta temporaria (o AnkiDroid pode estar com o banco travado)
            db = caminho_db
            try:
                import shutil
                import tempfile
                destino = os.path.join(tempfile.gettempdir(), "anki_tmp.anki2")
                shutil.copy2(caminho_db, destino)
                db = destino
            except Exception:
                db = caminho_db

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
            # alinha a primeira coluna com o dia da semana (domingo no topo)
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
            page.add(
                ft.Text(f"Heatmap {year}", size=24, color=BRANCO),
                ft.Text(f"{total} revisoes", size=13, color=CINZA),
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

        except Exception as ex:
            erro("Nao foi possivel gerar o heatmap: " + str(ex), traceback.format_exc())

    # ---------- diagnostico ----------
    def diagnostico(e=None):
        import os
        import sys

        linhas = []
        try:
            linhas.append("flet " + str(getattr(ft, "version", "?")))
        except Exception:
            pass
        linhas.append("python " + sys.version.split()[0])
        for p in PASTAS_BUSCA + [
            "/storage/emulated/0/AnkiDroid/collection.anki2",
            "/storage/emulated/0/Download",
        ]:
            try:
                linhas.append(("OK   " if os.path.exists(p) else "NAO  ") + p)
            except Exception as ex:
                linhas.append("ERR  " + p + " " + str(ex))

        limpar()
        page.add(
            ft.Text("Diagnostico", size=20, color=BRANCO),
            ft.Container(height=10),
            ft.Text("\n".join(linhas), size=11, color=CINZA, selectable=True),
            ft.Container(height=16),
            ft.ElevatedButton("Voltar", on_click=lambda _: tela_inicial()),
        )
        page.update()

    # ---------- tela inicial ----------
    def tela_inicial(e=None):
        limpar()
        controles = [
            ft.Container(height=20),
            ft.Text("Anki Heatmap", size=28, color=BRANCO),
            ft.Container(height=6),
            ft.Text("Carregue o seu collection.anki2", size=13, color=CINZA),
            ft.Container(height=24),
            ft.ElevatedButton("Procurar arquivo .anki2", on_click=procurar_arquivos,
                              width=280, height=48),
            ft.Container(height=10),
        ]
        if picker is not None:
            controles += [
                ft.ElevatedButton("Selecionar manualmente",
                                  on_click=lambda _: picker.pick_files(),
                                  width=280, height=48,
                                  bgcolor=AZUL, color=BRANCO),
                ft.Container(height=10),
            ]
        controles += [
            ft.ElevatedButton("Diagnostico", on_click=diagnostico, width=280, height=40),
            ft.Container(height=20),
            ft.Text(
                "Se nada funcionar, copie o collection.anki2\n"
                "para a pasta Download e procure de novo.",
                size=11, color=CINZA_ESC,
            ),
        ]
        page.add(*controles)
        page.update()

    tela_inicial()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
