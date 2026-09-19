import traceback

import flet as ft


def main(page: ft.Page):
    page.title = "Anki Heatmap"
    page.bgcolor = "#121212"
    page.padding = 20
    page.scroll = "auto"

    resultado = ft.Text("Nenhum arquivo selecionado ainda.", size=13, color="#B0B0B0", selectable=True)

    def ler_banco(caminho):
        import sqlite3

        try:
            resultado.value = "Lendo banco...\n" + caminho
            page.update()

            conn = sqlite3.connect(caminho)
            cur = conn.cursor()

            cur.execute("SELECT count(*) FROM revlog")
            total_revlog = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM cards")
            total_cards = cur.fetchone()[0]

            cur.execute("SELECT min(id), max(id) FROM revlog")
            min_id, max_id = cur.fetchone()

            conn.close()

            resultado.value = (
                "PASSO 4 OK - Banco lido com sucesso!\n\n"
                f"Caminho: {caminho}\n"
                f"Total de revisoes (revlog): {total_revlog}\n"
                f"Total de cartoes (cards): {total_cards}\n"
                f"Primeiro id revlog: {min_id}\n"
                f"Ultimo id revlog: {max_id}"
            )
        except Exception:
            resultado.value = "ERRO ao ler o banco:\n" + traceback.format_exc()
        page.update()

    def on_result(e: ft.FilePickerResultEvent):
        try:
            if e.files and len(e.files) > 0:
                caminho = e.files[0].path
                if caminho:
                    ler_banco(caminho)
                else:
                    resultado.value = "Caminho veio vazio (None)."
                    page.update()
            else:
                resultado.value = "Selecao cancelada ou vazia."
                page.update()
        except Exception:
            resultado.value = "ERRO no on_result:\n" + traceback.format_exc()
            page.update()

    picker = ft.FilePicker(on_result=on_result)

    try:
        if hasattr(page, "services"):
            page.services.append(picker)
        else:
            page.overlay.append(picker)
    except Exception:
        pass

    def abrir_picker(e):
        try:
            picker.pick_files()
        except Exception:
            resultado.value = "ERRO ao chamar pick_files:\n" + traceback.format_exc()
            page.update()

    page.add(
        ft.Text("PASSO 4 - Ler o SQLite", size=24, color="#FFFFFF"),
        ft.Container(height=16),
        ft.ElevatedButton("Selecionar collection.anki2", on_click=abrir_picker),
        ft.Container(height=16),
        resultado,
    )
    page.update()


ft.app(target=main)
