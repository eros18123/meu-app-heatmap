import flet as ft
import sqlite3
import datetime
import time
import os
import shutil
import tempfile
import traceback

# Cores em hexadecimal puro: nao dependem dos enums do Flet,
# que mudam de nome entre versoes (WHITE60 x WHITE_60 etc).
C_BRANCO = "#FFFFFF"
C_CINZA = "#B0B0B0"
C_CINZA_ESC = "#757575"
C_VAZIO = "#2A2A2A"
C_FUNDO_BOX = "#1C1C1C"
C_VERDE = "#2ecc71"
C_AMARELO = "#f1c40f"
C_VERMELHO = "#e74c3c"
C_AZUL = "#3498db"


def main(page: ft.Page):
    page.title = "Anki Heatmap"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#121212"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 20

    def avisar(texto):
        try:
            snack = ft.SnackBar(ft.Text(texto))
            if hasattr(page, "open"):
                page.open(snack)
            else:
                page.snack_bar = snack
                snack.open = True
                page.update()
        except Exception:
            pass

    def mostrar_erro(mensagem, erro_tecnico=""):
        # Esta tela precisa ser a prova de balas: so usa hex e widgets basicos.
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.add(
            ft.Text("ERRO", color="#e74c3c", weight=ft.FontWeight.BOLD, size=28),
            ft.Text(mensagem, color="#ff8a80", weight=ft.FontWeight.BOLD,
                    size=18, text_align=ft.TextAlign.CENTER),
            ft.Container(height=10),
            ft.Text(erro_tecnico, size=11, color=C_CINZA, selectable=True),
            ft.Container(height=20),
            ft.ElevatedButton("Voltar", on_click=lambda _: tela_inicial()),
        )
        page.update()

    try:
        file_picker = ft.FilePicker()

        def on_arquivo_selecionado(e):
            if e.files and len(e.files) > 0:
                caminho = e.files[0].path
                gerar_heatmap(caminho, datetime.datetime.now().year)
            else:
                avisar("Nenhum arquivo selecionado!")

        file_picker.on_result = on_arquivo_selecionado

        # Flet 1.x usa page.services; Flet 0.2x usa page.overlay.
        try:
            if hasattr(page, "services"):
                page.services.append(file_picker)
            else:
                page.overlay.append(file_picker)
        except Exception:
            page.overlay.append(file_picker)

        def gerar_heatmap(caminho_db, year):
            try:
                page.clean()
                page.vertical_alignment = ft.MainAxisAlignment.CENTER
                page.add(
                    ft.ProgressRing(color=C_VERDE),
                    ft.Container(height=15),
                    ft.Text("Lendo dados do Anki, aguarde...", size=16),
                )
                page.update()

                # Copia para pasta temporaria: o Anki pode estar com o banco travado.
                safe_db_path = caminho_db
                try:
                    temp_dir = tempfile.gettempdir()
                    destino = os.path.join(temp_dir, f"temp_anki_{year}.anki2")
                    shutil.copy2(caminho_db, destino)
                    safe_db_path = destino
                except Exception:
                    safe_db_path = caminho_db

                inicio = datetime.date(year, 1, 1)
                fim = datetime.date(year, 12, 31)
                dias_no_ano = (fim - inicio).days + 1

                start_ts = int(time.mktime(inicio.timetuple()) * 1000)
                end_ts = int(time.mktime((fim + datetime.timedelta(days=1)).timetuple()) * 1000)

                dados = {}
                max_count = 1

                conn = sqlite3.connect(safe_db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT strftime('%Y-%m-%d', id/1000.0, 'unixepoch', 'localtime'),
                           type, count()
                    FROM revlog
                    WHERE id >= ? AND id < ?
                    GROUP BY 1, 2
                    """,
                    (start_ts, end_ts),
                )
                for d_str, tipo, count in cursor.fetchall():
                    if d_str not in dados:
                        dados[d_str] = {"0": 0, "1": 0, "2": 0, "3": 0, "total": 0}
                    tipo_seguro = str(tipo) if str(tipo) in ["0", "1", "2", "3"] else "3"
                    dados[d_str][tipo_seguro] += count
                    dados[d_str]["total"] += count
                conn.close()

                if dados:
                    max_count = max(1, max(d["total"] for d in dados.values()))

                cores = {"0": C_VERDE, "1": C_AMARELO, "2": C_VERMELHO, "3": C_AZUL}
                pad = (inicio.weekday() + 1) % 7

                heatmap_row = ft.Row(scroll=ft.ScrollMode.ALWAYS, spacing=4)
                coluna_atual = ft.Column(spacing=4)

                for _ in range(pad):
                    coluna_atual.controls.append(
                        ft.Container(width=14, height=14, bgcolor="#00000000")
                    )

                for i in range(dias_no_ano):
                    data_atual = inicio + datetime.timedelta(days=i)
                    d_str = data_atual.strftime("%Y-%m-%d")

                    if d_str in dados:
                        dia = dados[d_str]
                        tipo_dom = max(["0", "1", "2", "3"], key=lambda k: dia[k])
                        quadrado = ft.Container(
                            width=14, height=14,
                            bgcolor=cores[tipo_dom],
                            border_radius=2,
                            opacity=max(0.3, min(1.0, dia["total"] / max_count)),
                            tooltip=(
                                f"{d_str}\nTotal: {dia['total']}\n"
                                f"Novos: {dia['0']} | Mad: {dia['1']}\n"
                                f"Apr: {dia['2']} | Filt: {dia['3']}"
                            ),
                        )
                    else:
                        quadrado = ft.Container(
                            width=14, height=14,
                            bgcolor=C_VAZIO,
                            border_radius=2,
                            tooltip=f"{d_str}\nNenhuma revisao",
                        )

                    coluna_atual.controls.append(quadrado)

                    if len(coluna_atual.controls) == 7:
                        heatmap_row.controls.append(coluna_atual)
                        coluna_atual = ft.Column(spacing=4)

                if len(coluna_atual.controls) > 0:
                    heatmap_row.controls.append(coluna_atual)

                total_ano = sum(d["total"] for d in dados.values()) if dados else 0

                botoes = ft.Row(
                    [
                        ft.ElevatedButton(
                            "< Ano Ant.",
                            on_click=lambda _: gerar_heatmap(caminho_db, year - 1),
                        ),
                        ft.ElevatedButton(
                            "Prox. Ano >",
                            on_click=lambda _: gerar_heatmap(caminho_db, year + 1),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                )

                page.clean()
                page.vertical_alignment = ft.MainAxisAlignment.START
                page.add(
                    ft.Container(height=30),
                    ft.Text(f"Heatmap {year}", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{total_ano} revisoes no ano", size=13, color=C_CINZA),
                    ft.Container(height=10),
                    botoes,
                    ft.Container(height=20),
                    ft.Container(
                        content=heatmap_row,
                        padding=10,
                        bgcolor=C_FUNDO_BOX,
                        border_radius=10,
                    ),
                    ft.Container(height=20),
                    ft.ElevatedButton("Voltar ao Inicio", on_click=lambda _: tela_inicial()),
                )
                page.update()

            except Exception:
                mostrar_erro("Nao foi possivel gerar o Heatmap", traceback.format_exc())

        def buscar_automaticamente(e):
            caminhos_padrao = [
                "/storage/emulated/0/AnkiDroid/collection.anki2",
                "/sdcard/AnkiDroid/collection.anki2",
                "/storage/emulated/0/Android/data/com.ichi2.anki/files/AnkiDroid/collection.anki2",
            ]

            db_encontrado = None
            for path in caminhos_padrao:
                try:
                    if os.path.exists(path):
                        db_encontrado = path
                        break
                except Exception:
                    continue

            if db_encontrado:
                try:
                    conn = sqlite3.connect(db_encontrado)
                    conn.execute("SELECT 1 FROM revlog LIMIT 1")
                    conn.close()
                    gerar_heatmap(db_encontrado, datetime.datetime.now().year)
                except Exception as ex:
                    mostrar_erro(
                        "O Android bloqueou a leitura automatica.",
                        "Use o botao manual.\nDetalhe: " + str(ex),
                    )
            else:
                avisar("Nao achei a pasta do Anki. Use a busca manual.")

        def tela_inicial():
            page.clean()
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.add(
                ft.Text("Anki Heatmap", size=28, weight=ft.FontWeight.BOLD, color=C_BRANCO),
                ft.Container(height=10),
                ft.Text(
                    "Escolha como carregar seus dados:",
                    text_align=ft.TextAlign.CENTER,
                    color=C_CINZA,
                ),
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Buscar Automaticamente",
                    on_click=buscar_automaticamente,
                    width=300, height=50,
                ),
                ft.Container(height=10),
                ft.ElevatedButton(
                    "Selecionar Manualmente",
                    on_click=lambda _: file_picker.pick_files(),
                    width=300, height=50,
                    bgcolor=C_AZUL, color=C_BRANCO,
                ),
                ft.Container(height=20),
                ft.Text(
                    "Dica: navegue ate 'AnkiDroid' -> 'collection.anki2'",
                    size=12, color=C_CINZA_ESC, text_align=ft.TextAlign.CENTER,
                ),
            )
            page.update()

        tela_inicial()

    except Exception:
        mostrar_erro("Erro Critico ao Iniciar", traceback.format_exc())


if __name__ == "__main__":
    # Flet 1.x: ft.run(main) | Flet 0.2x: ft.app(target=main)
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
