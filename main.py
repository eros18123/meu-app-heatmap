import flet as ft
import sqlite3
import datetime
import time
import os
import shutil
import tempfile
import traceback

def main(page: ft.Page):
    # 1. Garante que o app desenhe o fundo imediatamente para evitar a TELA PRETA
    page.title = "Anki Heatmap"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # TELA DE CARREGAMENTO INICIAL
    loading_text = ft.Text("Procurando banco de dados...", size=18)
    page.add(
        ft.ProgressRing(color=ft.Colors.GREEN_400),
        ft.Container(height=20),
        loading_text
    )
    page.update()

    try:
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                selected_path = e.files[0].path
                ano_atual = datetime.datetime.now().year
                show_heatmap(ano_atual, selected_path)
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Nenhum arquivo selecionado!"))
                page.snack_bar.open = True
                page.update()

        file_picker = ft.FilePicker(on_result=on_dialog_result)
        page.overlay.append(file_picker)

        def show_heatmap(year, db_path):
            page.clean()
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            
            # Mostra o carregamento enquanto copia e lê o DB pesado
            page.add(
                ft.ProgressRing(color=ft.Colors.BLUE), 
                ft.Container(height=10),
                ft.Text("Lendo estudos do Anki...")
            )
            page.update()

            temp_dir = tempfile.gettempdir()
            safe_db_path = os.path.join(temp_dir, f"temp_anki_{year}.anki2")
            try:
                shutil.copy2(db_path, safe_db_path)
            except:
                safe_db_path = db_path 

            inicio = datetime.date(year, 1, 1)
            fim = datetime.date(year, 12, 31)
            dias_no_ano = (fim - inicio).days + 1
            
            start_ts = int(time.mktime(inicio.timetuple()) * 1000)
            end_ts = int(time.mktime((fim + datetime.timedelta(days=1)).timetuple()) * 1000)

            dados = {}
            max_count = 1
            
            try:
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
            except Exception as e:
                page.clean()
                page.add(
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED, size=50),
                    ft.Text("Falha ao ler o arquivo!", color=ft.Colors.RED, weight="bold", size=20),
                    ft.Text(f"Erro: {str(e)}", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=20),
                    ft.ElevatedButton("Tentar Novamente", icon=ft.Icons.SYNC, on_click=lambda _: file_picker.pick_files())
                )
                page.update()
                return

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
                ft.Button("<- Ano Ant.", on_click=lambda _: show_heatmap(year - 1, db_path)),
                ft.Button("Prox. Ano ->", on_click=lambda _: show_heatmap(year + 1, db_path)),
            ], alignment=ft.MainAxisAlignment.CENTER)

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
                ft.ElevatedButton("Atualizar (Sincronizar)", icon=ft.Icons.SYNC, on_click=lambda _: file_picker.pick_files())
            )
            page.update()

        # Dá um respiro pro celular renderizar a bolinha girando antes de procurar o arquivo
        time.sleep(0.5)

        caminhos_padrao = [
            "/storage/emulated/0/AnkiDroid/collection.anki2",
            "/sdcard/AnkiDroid/collection.anki2"
        ]
        
        db_legivel = None
        for path in caminhos_padrao:
            if os.path.exists(path):
                try:
                    temp_dir = tempfile.gettempdir()
                    test_path = os.path.join(temp_dir, "test_perm.anki2")
                    shutil.copy2(path, test_path)
                    
                    conn = sqlite3.connect(test_path)
                    conn.execute("SELECT 1 FROM revlog LIMIT 1")
                    conn.close()
                    
                    db_legivel = test_path
                    break
                except Exception:
                    pass 

        ano_atual = datetime.datetime.now().year

        if db_legivel:
            show_heatmap(ano_atual, db_legivel)
        else:
            page.clean()
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.add(
                ft.Icon(ft.Icons.LOCK_OUTLINE, size=80, color=ft.Colors.ORANGE),
                ft.Text("Arquivo não encontrado", size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text("Por favor, clique abaixo e selecione o arquivo 'collection.anki2' manualmente.", text_align=ft.TextAlign.CENTER),
                ft.Container(height=20),
                ft.ElevatedButton("Selecionar Arquivo", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: file_picker.pick_files(), bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE)
            )
            page.update()

    except Exception as e:
        # SE ALGO MAIS DER ERRADO, MOSTRA NA TELA EM VEZ DE FICAR TELA PRETA
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        err_msg = traceback.format_exc()
        page.add(
            ft.Icon(ft.Icons.BUG_REPORT, size=80, color=ft.Colors.RED),
            ft.Text("Ocorreu um erro interno:", color=ft.Colors.RED, weight="bold"),
            ft.Text(err_msg, size=12, selectable=True, color=ft.Colors.WHITE)
        )
        page.update()

if __name__ == '__main__':
    ft.app(target=main)
