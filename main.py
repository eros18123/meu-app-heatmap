import flet as ft
import sqlite3
import datetime
import time
import os
import shutil
import tempfile
import traceback

def main(page: ft.Page):
    # 1. Configurações Iniciais da Tela
    page.title = "Anki Heatmap"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.padding = 20

    # 2. Função para mostrar erros na tela (em vez de fechar ou ficar preto)
    def mostrar_erro(mensagem, erro_tecnico=""):
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.add(
            ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED_500, size=60),
            ft.Text(mensagem, color=ft.Colors.RED_300, weight="bold", size=20, text_align=ft.TextAlign.CENTER),
            ft.Container(height=10),
            ft.Text(erro_tecnico, size=12, color=ft.Colors.WHITE60, selectable=True),
            ft.Container(height=20),
            ft.ElevatedButton("Voltar ao Início", icon=ft.Icons.HOME, on_click=lambda _: tela_inicial())
        )
        page.update()

    # 3. Lógica Pesada: Ler Banco de Dados e Gerar Heatmap
    def gerar_heatmap(caminho_db, year):
        try:
            # Mostra que está carregando...
            page.clean()
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.add(
                ft.ProgressRing(color=ft.Colors.GREEN),
                ft.Container(height=15),
                ft.Text("Lendo dados do Anki, por favor aguarde...", size=16)
            )
            page.update()

            # Truque para burlar arquivo trancado: copia para área temporária
            temp_dir = tempfile.gettempdir()
            safe_db_path = os.path.join(temp_dir, f"temp_anki_{year}.anki2")
            try:
                shutil.copy2(caminho_db, safe_db_path)
            except Exception:
                safe_db_path = caminho_db

            # Lógica de datas
            inicio = datetime.date(year, 1, 1)
            fim = datetime.date(year, 12, 31)
            dias_no_ano = (fim - inicio).days + 1
            
            start_ts = int(time.mktime(inicio.timetuple()) * 1000)
            end_ts = int(time.mktime((fim + datetime.timedelta(days=1)).timetuple()) * 1000)

            dados = {}
            max_count = 1
            
            # Consultando o Banco
            conn = sqlite3.connect(safe_db_path)
            cursor = conn.cursor()
            query = f"""
                SELECT strftime('%Y-%m-%d', id/1000.0, 'unixepoch', 'localtime'), type, count() 
                FROM revlog WHERE id >= {start_ts} AND id < {end_ts} GROUP BY 1, 2
            """
            cursor.execute(query)
            for d_str, tipo, count in cursor.fetchall():
                if d_str not in dados:
                    dados[d_str] = {'0':0, '1':0, '2':0, '3':0, 'total': 0}
                tipo_seguro = str(tipo) if str(tipo) in ['0', '1', '2', '3'] else '3'
                dados[d_str][tipo_seguro] += count
                dados[d_str]['total'] += count
            conn.close()
            
            if dados:
                max_count = max([d['total'] for d in dados.values()])

            # Montando o Calendário Gráfico
            cores = {'0': "#2ecc71", '1': "#f1c40f", '2': "#e74c3c", '3': "#3498db"}
            pad = (inicio.weekday() + 1) % 7 

            heatmap_row = ft.Row(scroll=ft.ScrollMode.ALWAYS, spacing=4)
            coluna_atual = ft.Column(spacing=4)

            for _ in range(pad):
                coluna_atual.controls.append(ft.Container(width=14, height=14, bgcolor=ft.Colors.TRANSPARENT))

            for i in range(dias_no_ano):
                data_atual = inicio + datetime.timedelta(days=i)
                d_str = data_atual.strftime("%Y-%m-%d")

                if d_str in dados:
                    dia = dados[d_str]
                    tipo_dom = max(['0', '1', '2', '3'], key=lambda k: dia[k])
                    quadrado = ft.Container(
                        width=14, height=14, 
                        bgcolor=cores[tipo_dom], 
                        border_radius=2,
                        opacity=max(0.3, dia['total'] / max_count),
                        tooltip=f"{d_str}\nTotal: {dia['total']}\nNovos: {dia['0']} | Mad: {dia['1']}\nApr: {dia['2']} | Filt: {dia['3']}"
                    )
                else:
                    quadrado = ft.Container(
                        width=14, height=14, 
                        bgcolor=ft.Colors.WHITE_10, 
                        border_radius=2,
                        tooltip=f"{d_str}\nNenhuma revisão"
                    )

                coluna_atual.controls.append(quadrado)

                if len(coluna_atual.controls) == 7:
                    heatmap_row.controls.append(coluna_atual)
                    coluna_atual = ft.Column(spacing=4)

            if len(coluna_atual.controls) > 0:
                heatmap_row.controls.append(coluna_atual)

            botoes = ft.Row([
                ft.Button("<- Ano Ant.", on_click=lambda _: gerar_heatmap(caminho_db, year - 1)),
                ft.Button("Prox. Ano ->", on_click=lambda _: gerar_heatmap(caminho_db, year + 1)),
            ], alignment=ft.MainAxisAlignment.CENTER)

            # Exibe o Mapa Prontinho
            page.clean()
            page.vertical_alignment = ft.MainAxisAlignment.START
            page.add(
                ft.Container(height=40),
                ft.Text(f"Heatmap {year}", size=24, weight=ft.FontWeight.BOLD),
                botoes,
                ft.Container(height=20),
                ft.Container(
                    content=heatmap_row,
                    padding=10,
                    bgcolor=ft.Colors.BLACK_12,
                    border_radius=10
                ),
                ft.Container(height=20),
                ft.ElevatedButton("Início", icon=ft.Icons.HOME, on_click=lambda _: tela_inicial())
            )
            page.update()

        except Exception as e:
            mostrar_erro("Não foi possível gerar o Heatmap", traceback.format_exc())

    # 4. Buscador Automático de Pastas
    def buscar_automaticamente(e):
        caminhos_padrao = [
            "/storage/emulated/0/AnkiDroid/collection.anki2",
            "/sdcard/AnkiDroid/collection.anki2"
        ]
        
        db_encontrado = None
        for path in caminhos_padrao:
            if os.path.exists(path):
                db_encontrado = path
                break
        
        if db_encontrado:
            try:
                # Testa se o app tem permissão para ler
                conn = sqlite3.connect(db_encontrado)
                conn.execute("SELECT 1 FROM revlog LIMIT 1")
                conn.close()
                gerar_heatmap(db_encontrado, datetime.datetime.now().year)
            except Exception as ex:
                mostrar_erro("Arquivo encontrado, mas o Android bloqueou a leitura automática.", "Use o botão de 'Selecionar Manualmente' para dar permissão.\nErro: " + str(ex))
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Não achei a pasta do Anki automaticamente! Use a busca manual."))
            page.snack_bar.open = True
            page.update()

    # 5. Seletor Manual de Arquivo (Quando o usuário escolhe o arquivo)
    def on_arquivo_selecionado(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            caminho_selecionado = e.files[0].path
            ano_atual = datetime.datetime.now().year
            gerar_heatmap(caminho_selecionado, ano_atual)
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Nenhum arquivo selecionado!"))
            page.snack_bar.open = True
            page.update()

    file_picker = ft.FilePicker(on_result=on_arquivo_selecionado)
    page.overlay.append(file_picker)

    # 6. TELA INICIAL (A primeira coisa que aparece sem travar)
    def tela_inicial():
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.add(
            ft.Icon(ft.Icons.ANALYTICS, size=80, color=ft.Colors.BLUE),
            ft.Text("Anki Heatmap", size=28, weight="bold"),
            ft.Container(height=10),
            ft.Text("Escolha como carregar seus dados do AnkiDroid:", text_align=ft.TextAlign.CENTER, color=ft.Colors.WHITE70),
            ft.Container(height=30),
            
            ft.ElevatedButton(
                "1. Buscar Automaticamente", 
                icon=ft.Icons.SEARCH, 
                on_click=buscar_automaticamente,
                width=300, height=50
            ),
            ft.Container(height=10),
            ft.ElevatedButton(
                "2. Selecionar Manualmente", 
                icon=ft.Icons.FOLDER_OPEN, 
                on_click=lambda _: file_picker.pick_files(),
                width=300, height=50,
                bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE
            ),
            ft.Container(height=20),
            ft.Text("Dica manual: Vá nas pastas até achar 'AnkiDroid' -> 'collection.anki2'", size=12, color=ft.Colors.WHITE54, text_align=ft.TextAlign.CENTER)
        )
        page.update()

    # Inicia o app renderizando a tela de botões IMEDIATAMENTE
    tela_inicial()

if __name__ == '__main__':
    ft.app(target=main)
