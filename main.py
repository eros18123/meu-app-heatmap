import flet as ft


def main(page: ft.Page):
    page.title = "Anki Heatmap"
    page.bgcolor = "#121212"
    page.padding = 20

    def ir_para_tela_2(e):
        page.controls.clear()
        page.add(
            ft.Text("PASSO 2 - TELA B", size=30, color="#FFFFFF"),
            ft.ElevatedButton("Voltar", on_click=ir_para_tela_1),
        )
        page.update()

    def ir_para_tela_1(e):
        page.controls.clear()
        page.add(
            ft.Text("PASSO 2 OK", size=30, color="#FFFFFF"),
            ft.Text("Se voce esta vendo isso, botoes funcionam.", size=14, color="#B0B0B0"),
            ft.ElevatedButton("Ir para tela B", on_click=ir_para_tela_2),
        )
        page.update()

    ir_para_tela_1(None)


ft.app(target=main)
