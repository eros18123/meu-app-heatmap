import flet as ft


def main(page: ft.Page):
    page.title = "Anki Heatmap"
    page.bgcolor = "#121212"
    page.padding = 20

    resultado = ft.Text("Nenhum arquivo selecionado ainda.", size=13, color="#B0B0B0", selectable=True)

    def on_result(e: ft.FilePickerResultEvent):
        try:
            if e.files and len(e.files) > 0:
                caminho = e.files[0].path
                resultado.value = "CAMINHO RECEBIDO:\n" + str(caminho)
            else:
                resultado.value = "Selecao cancelada ou vazia."
        except Exception as ex:
            resultado.value = "ERRO no on_result:\n" + str(ex)
        page.update()

    picker = ft.FilePicker(on_result=on_result)

    # Registrar o picker: no Flet 1.x usa page.services, no 0.2x usa page.overlay
    registrado_em = "desconhecido"
    try:
        if hasattr(page, "services"):
            page.services.append(picker)
            registrado_em = "page.services"
        else:
            page.overlay.append(picker)
            registrado_em = "page.overlay"
    except Exception as ex:
        registrado_em = "FALHOU: " + str(ex)

    def abrir_picker(e):
        try:
            picker.pick_files()
        except Exception as ex:
            resultado.value = "ERRO ao chamar pick_files:\n" + str(ex)
            page.update()

    page.add(
        ft.Text("PASSO 3 - FilePicker", size=26, color="#FFFFFF"),
        ft.Text("Registrado em: " + registrado_em, size=12, color="#8A8A8A"),
        ft.Container(height=16),
        ft.ElevatedButton("Selecionar arquivo", on_click=abrir_picker),
        ft.Container(height=16),
        resultado,
    )
    page.update()


ft.app(target=main)
