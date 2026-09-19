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
CORES = {"0": VERDE, "1": AMARELO, "2": VERMELHO, "3": AZUL}
NOMES_MES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

PASTAS_BUSCA = ["/storage/emulated/0", "/sdcard", "/storage"]
NOME_ARQUIVO_PERSISTENTE = "anki_heatmap_cache.db"


def main(page: ft.Page):
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
    for attr, valor in [("title", "Anki Heatmap"), ("bgcolor", "#121212"), ("padding", 16)]:
        try:
            setattr(page, attr, valor)
        except Exception:
            pass
    try:
        page.scroll = "auto"
    except Exception:
        pass

    estado = {"db": None, "ano": None, "mes": None}

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

    # ---------- armazenamento persistente ----------
    def dir_dados_app():
        import os
        import tempfile

        caminho = os.getenv("FLET_APP_STORAGE_DATA")
        try:
            if caminho and os.path.isdir(caminho):
                return caminho
        except Exception:
            pass
        return tempfile.gettempdir()

    def caminho_persistente():
        import os
        return os.path.join(dir_dados_app(), NOME_ARQUIVO_PERSISTENTE)

    def salvar_persistente(destino, diag):
        import os
        import shutil

        try:
            pers = caminho_persistente()
            if os.path.abspath(destino) != os.path.abspath(pers):
                shutil.copy2(destino, pers)
        except Exception:
            pass
        return destino, diag

    # ---------- extracao do banco (zip/.colpkg, .anki2 puro, zstd) ----------
    def preparar_banco(caminho_original):
        import os
        import shutil
        import tempfile
        import zipfile

        temp_dir = tempfile.gettempdir()
        copia = os.path.join(temp_dir, "anki_original_tmp")
        shutil.copy2(caminho_original, copia)

        diag = {"e_zip": False, "entradas": [], "escolhido": None, "tamanho": None}

        if not zipfile.is_zipfile(copia):
            destino = os.path.join(temp_dir, "anki_db_tmp.anki2")
            shutil.copy2(copia, destino)
            diag["tamanho"] = os.path.getsize(destino)
            return salvar_persistente(destino, diag)

        diag["e_zip"] = True
        with zipfile.ZipFile(copia, "r") as z:
            nomes = z.namelist()
            diag["entradas"] = nomes

            if "collection.anki21b" in nomes:
                try:
                    import zstandard
                except Exception as ex:
                    raise RuntimeError(
                        "O backup usa compactacao zstd, mas a biblioteca "
                        "'zstandard' nao carregou neste build.\n"
                        f"Detalhe: {ex}"
                    )
                diag["escolhido"] = "collection.anki21b (descomprimido com zstd)"
                destino = os.path.join(temp_dir, "anki_db_tmp.anki2")
                dctx = zstandard.ZstdDecompressor()
                with z.open("collection.anki21b") as origem:
                    with dctx.stream_reader(origem) as reader, open(destino, "wb") as saida:
                        shutil.copyfileobj(reader, saida)
                diag["tamanho"] = os.path.getsize(destino)
                return salvar_persistente(destino, diag)

            escolhido = None
            for nome in ["collection.anki21", "collection.anki2"]:
                if nome in nomes:
                    escolhido = nome
                    break

            if escolhido is None:
                raise RuntimeError(
                    "Nao encontrei um banco de dados reconhecivel dentro "
                    "deste backup.\n\nArquivos encontrados:\n"
                    + "\n".join(nomes[:15])
                )

            diag["escolhido"] = escolhido
            destino = os.path.join(temp_dir, "anki_db_tmp.anki2")
            with z.open(escolhido) as origem, open(destino, "wb") as saida:
                shutil.copyfileobj(origem, saida)
            diag["tamanho"] = os.path.getsize(destino)
            return salvar_persistente(destino, diag)

    def texto_diagnostico(diag):
        linhas = [
            f"E arquivo zip (.colpkg/.apkg): {diag.get('e_zip')}",
            f"Arquivo escolhido de dentro: {diag.get('escolhido')}",
            f"Tamanho do banco extraido: {diag.get('tamanho')} bytes",
        ]
        if diag.get("e_zip"):
            linhas.append("Entradas do zip: " + ", ".join(diag.get("entradas", [])[:20]))
        if "tabelas" in diag:
            linhas.append("Tabelas no banco: " + ", ".join(diag["tabelas"]))
        if "linhas_revlog" in diag:
            linhas.append(f"Linhas na tabela revlog: {diag['linhas_revlog']}")
        return "\n".join(linhas)

    # ---------- dados ----------
    def ano_mes_mais_recentes(caminho_db):
        import datetime
        import sqlite3

        try:
            db, _diag = preparar_banco(caminho_db)
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute("SELECT max(id) FROM revlog")
            max_id = cur.fetchone()[0]
            conn.close()
            if max_id:
                dt = datetime.datetime.fromtimestamp(max_id / 1000)
                return dt.year, dt.month
        except Exception:
            pass
        agora = datetime.datetime.now()
        return agora.year, agora.month

    def carregar_dados_ano(caminho_original, year):
        import datetime
        import sqlite3
        import time

        db, diag = preparar_banco(caminho_original)

        inicio = datetime.date(year, 1, 1)
        fim = datetime.date(year, 12, 31)
        ini_ts = int(time.mktime(inicio.timetuple()) * 1000)
        fim_ts = int(time.mktime((fim + datetime.timedelta(days=1)).timetuple()) * 1000)

        dados = {}
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        diag["tabelas"] = [r[0] for r in cur.fetchall()]
        if "revlog" in diag["tabelas"]:
            cur.execute("SELECT count(*) FROM revlog")
            diag["linhas_revlog"] = cur.fetchone()[0]
        else:
            diag["linhas_revlog"] = 0

        cur.execute(
            "SELECT strftime('%Y-%m-%d', id/1000.0, 'unixepoch', 'localtime'),"
            " type, count(), sum(time) FROM revlog"
            " WHERE id >= ? AND id < ? GROUP BY 1, 2",
            (ini_ts, fim_ts),
        )
        for d_str, tipo, qtd, tempo in cur.fetchall():
            if d_str not in dados:
                dados[d_str] = {"0": 0, "1": 0, "2": 0, "3": 0, "total": 0, "tempo_ms": 0}
            t = str(tipo) if str(tipo) in ("0", "1", "2", "3") else "3"
            dados[d_str][t] += qtd
            dados[d_str]["total"] += qtd
            dados[d_str]["tempo_ms"] += tempo or 0
        conn.close()
        return dados, diag

    # ---------- dialogo de info do dia ----------
    def fechar_dialogo(dlg):
        try:
            if hasattr(page, "close"):
                page.close(dlg)
            else:
                dlg.open = False
                page.update()
        except Exception:
            pass

    def mostrar_dialogo(titulo, linhas):
        dlg = ft.AlertDialog(
            title=ft.Text(titulo),
            content=ft.Text("\n".join(linhas), selectable=True),
        )
        dlg.actions = [ft.TextButton("Fechar", on_click=lambda e: fechar_dialogo(dlg))]
        try:
            if hasattr(page, "open"):
                page.open(dlg)
            else:
                page.dialog = dlg
                dlg.open = True
                page.update()
        except Exception:
            pass

    def mostrar_info_dia(data_str, info):
        if not info:
            mostrar_dialogo(data_str, ["Nenhuma revisao neste dia."])
            return
        minutos = round((info["tempo_ms"] or 0) / 60000, 1)
        linhas = [
            f"Total de cartoes: {info['total']}",
            f"Novos: {info['0']}   Maduros: {info['1']}",
            f"Aprendendo: {info['2']}   Filtrados: {info['3']}",
            f"Tempo estudado: {minutos} min",
        ]
        mostrar_dialogo(data_str, linhas)

    # ---------- grade do mes ----------
    def montar_grade_mes(dados, year, month):
        import calendar
        import datetime

        primeiro = datetime.date(year, month, 1)
        dias_no_mes = calendar.monthrange(year, month)[1]
        pad = (primeiro.weekday() + 1) % 7  # domingo primeiro

        valores = []
        for d in range(1, dias_no_mes + 1):
            s = datetime.date(year, month, d).strftime("%Y-%m-%d")
            valores.append(dados.get(s, {"total": 0})["total"])
        maximo = max(1, max(valores) if valores else 1)

        tamanho = 36
        linhas = []
        semana = [ft.Container(width=tamanho, height=tamanho) for _ in range(pad)]

        for d in range(1, dias_no_mes + 1):
            data_obj = datetime.date(year, month, d)
            s = data_obj.strftime("%Y-%m-%d")
            info = dados.get(s)
            if info:
                dom = max(("0", "1", "2", "3"), key=lambda k: info[k])
                cor = CORES[dom]
                op = max(0.35, min(1.0, info["total"] / maximo))
                cor_texto = BRANCO
            else:
                cor = VAZIO
                op = 1.0
                cor_texto = CINZA_ESC

            quadrado = ft.Container(
                width=tamanho, height=tamanho, border_radius=6,
                bgcolor=cor, opacity=op,
                alignment=ft.alignment.center,
                content=ft.Text(str(d), size=11, color=cor_texto),
                on_click=lambda e, ss=s, ii=info: mostrar_info_dia(ss, ii),
            )
            semana.append(quadrado)
            if len(semana) == 7:
                linhas.append(ft.Row(semana, spacing=6))
                semana = []

        if semana:
            while len(semana) < 7:
                semana.append(ft.Container(width=tamanho, height=tamanho))
            linhas.append(ft.Row(semana, spacing=6))

        return ft.Column(linhas, spacing=6)

    def montar_abas_mes(mes_selecionado, ao_clicar):
        botoes = []
        for i in range(1, 13):
            sel = i == mes_selecionado
            botoes.append(
                ft.ElevatedButton(
                    NOMES_MES[i - 1],
                    bgcolor=AZUL if sel else CAIXA,
                    color=BRANCO,
                    on_click=lambda e, m=i: ao_clicar(m),
                )
            )
        return ft.Row(botoes, scroll="always", spacing=6)

    # ---------- tela principal do heatmap ----------
    def mostrar_mes(caminho_original, year, month):
        try:
            limpar()
            page.add(
                ft.Text(f"Carregando {NOMES_MES[month - 1]} {year}...", size=16, color=BRANCO),
                ft.ProgressRing(color=VERDE),
            )
            page.update()

            dados, diag = carregar_dados_ano(caminho_original, year)
            estado["db"] = caminho_original
            estado["ano"] = year
            estado["mes"] = month

            total_mes = sum(
                v["total"] for k, v in dados.items()
                if k.startswith(f"{year:04d}-{month:02d}")
            )
            total_ano = sum(v["total"] for v in dados.values())

            limpar()
            blocos = [
                ft.Text("Anki Heatmap", size=22, color=BRANCO),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "< " + str(year - 1),
                            on_click=lambda e: mostrar_mes(caminho_original, year - 1, month),
                        ),
                        ft.Text(str(year), size=18, color=BRANCO, weight=ft.FontWeight.BOLD),
                        ft.ElevatedButton(
                            str(year + 1) + " >",
                            on_click=lambda e: mostrar_mes(caminho_original, year + 1, month),
                        ),
                    ],
                    alignment="center",
                ),
                ft.Container(height=6),
                montar_abas_mes(month, lambda m: mostrar_mes(caminho_original, year, m)),
                ft.Container(height=10),
                ft.Text(f"{NOMES_MES[month - 1]} {year}: {total_mes} revisoes", size=14, color=CINZA),
                ft.Text(f"Ano inteiro: {total_ano} revisoes", size=11, color=CINZA_ESC),
                ft.Container(height=10),
            ]

            if total_ano == 0:
                blocos.append(
                    ft.Text(
                        "--- DIAGNOSTICO ---\n" + texto_diagnostico(diag),
                        size=11, color=AMARELO, selectable=True,
                    )
                )

            blocos.append(
                ft.Container(
                    content=montar_grade_mes(dados, year, month),
                    padding=12, bgcolor=CAIXA, border_radius=10,
                )
            )
            blocos.append(ft.Container(height=10))
            blocos.append(
                ft.Row(
                    [
                        ft.Text("verde novo", size=10, color=VERDE),
                        ft.Text("amarelo maduro", size=10, color=AMARELO),
                        ft.Text("vermelho aprendendo", size=10, color=VERMELHO),
                        ft.Text("azul filtrado", size=10, color=AZUL),
                    ],
                    wrap=True, spacing=10,
                )
            )
            blocos.append(ft.Container(height=14))
            blocos.append(ft.ElevatedButton("Trocar arquivo", on_click=lambda e: tela_inicial()))

            page.add(*blocos)
            page.update()

        except Exception:
            erro("Nao foi possivel gerar o heatmap", traceback.format_exc())

    # ---------- file picker ----------
    def on_pick(e):
        try:
            if getattr(e, "files", None):
                caminho = e.files[0].path
                if caminho:
                    ano, mes = ano_mes_mais_recentes(caminho)
                    mostrar_mes(caminho, ano, mes)
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
            ft.Text("Procurando arquivos .anki2/.colpkg...", size=16, color=BRANCO),
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
                        if nome.endswith(".anki2") or nome.endswith(".colpkg"):
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
                ft.Text("Nenhum arquivo encontrado automaticamente", size=18, color=BRANCO),
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
                ano, mes = ano_mes_mais_recentes(c)
                mostrar_mes(c, ano, mes)

            itens.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(caminho, size=11, color=CINZA, selectable=True),
                            ft.ElevatedButton("Usar este", on_click=usar),
                        ],
                        spacing=6,
                    ),
                    bgcolor=CAIXA, padding=10, border_radius=8,
                )
            )
            itens.append(ft.Container(height=8))

        itens.append(ft.ElevatedButton("Voltar", on_click=lambda _: tela_inicial()))
        page.add(*itens)
        page.update()

    # ---------- tela inicial ----------
    def tela_inicial(e=None):
        limpar()
        page.add(
            ft.Container(height=20),
            ft.Text("Anki Heatmap", size=28, color=BRANCO),
            ft.Container(height=6),
            ft.Text("Carregue seu collection.anki2 ou .colpkg", size=13, color=CINZA),
            ft.Container(height=24),
            ft.ElevatedButton("Procurar automaticamente", on_click=procurar_arquivos,
                              width=280, height=48),
            ft.Container(height=10),
            ft.ElevatedButton("Selecionar manualmente",
                              on_click=lambda _: picker.pick_files(),
                              width=280, height=48,
                              bgcolor=AZUL, color=BRANCO),
            ft.Container(height=20),
            ft.Text(
                "Depois de escolher uma vez, o app lembra\n"
                "automaticamente na proxima abertura.",
                size=11, color=CINZA_ESC,
            ),
        )
        page.update()

    # ---------- autocarregar cache persistente ----------
    def tentar_autocarregar():
        import os

        try:
            p = caminho_persistente()
            if os.path.exists(p) and os.path.getsize(p) > 0:
                ano, mes = ano_mes_mais_recentes(p)
                mostrar_mes(p, ano, mes)
                return True
        except Exception:
            pass
        return False

    if not tentar_autocarregar():
        tela_inicial()


ft.app(target=main)
