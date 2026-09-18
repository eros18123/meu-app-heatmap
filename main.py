import flet as ft
import sqlite3
import datetime
import time
import os

# Caminho do seu banco de dados para testar no PC
ANKI_DB_PATH = r"C:\Users\eros\Desktop\anki novo\aaa\teste\collection.anki2"

def main(page: ft.Page):
    # Configurações visuais do App
    page.title = "Anki Heatmap"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    
    page.window.width = 400  
    page.window.height = 700

    # ==========================================
    # TELA DE HEATMAP
    # ==========================================
    def show_heatmap(year):
        page.clean()  # Limpa a tela de login
        page.vertical_alignment = ft.MainAxisAlignment.START

        # Lógica de datas e SQLite (igual ao seu Add-on)
        inicio = datetime.date(year, 1, 1)
        fim = datetime.date(year, 12, 31)
        dias_no_ano = (fim - inicio).days + 1
        
        start_ts = int(time.mktime(inicio.timetuple()) * 1000)
        end_ts = int(time.mktime((fim + datetime.timedelta(days=1)).timetuple()) * 1000)

        dados = {}
        max_count = 1
        
        if os.path.exists(ANKI_DB_PATH):
            try:
                conn = sqlite3.connect(ANKI_DB_PATH)
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
            except sqlite3.OperationalError:
                pass # Ignora erro de lock no protótipo

        # Cores (Formato HEX pro Flet)
        cores = {'0': "#2ecc71", '1': "#f1c40f", '2': "#e74c3c", '3': "#3498db"}

        pad = (inicio.weekday() + 1) % 7 

        # Construindo o Calendário
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
                
                # CORRIGIDO: O texto do tooltip agora fica direto na propriedade do Container!
                quadrado = ft.Container(
                    width=14, height=14, 
                    bgcolor=cores[tipo_dom], 
                    border_radius=2,
                    opacity=max(0.3, dia['total'] / max_count),
                    tooltip=f"{d_str}\nTotal: {dia['total']}\nNovos: {dia['0']} | Mad: {dia['1']}\nApr: {dia['2']} | Filt: {dia['3']}"
                )
            else:
                # CORRIGIDO AQUI TAMBÉM!
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
            ft.Button("<- Ano Ant.", on_click=lambda _: show_heatmap(year - 1)),
            ft.Button("Prox. Ano ->", on_click=lambda _: show_heatmap(year + 1)),
        ], alignment=ft.MainAxisAlignment.CENTER)

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
            ft.Button("Sair", color=ft.Colors.RED_300, on_click=lambda _: show_login())
        )
        page.update()

    # ==========================================
    # TELA DE LOGIN
    # ==========================================
    def show_login():
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        
        user_input = ft.TextField(label="Usuário (usuario)", width=300, bgcolor=ft.Colors.WHITE_10)
        pass_input = ft.TextField(label="Senha (senha123)", password=True, width=300, bgcolor=ft.Colors.WHITE_10)
        
        def btn_login_click(e):
            if user_input.value == "usuario" and pass_input.value == "senha123":
                show_heatmap(2026)
            else:
                page.open(ft.SnackBar(ft.Text("Login incorreto!")))

        page.add(
            ft.Icon(ft.Icons.MAP_OUTLINED, size=80, color=ft.Colors.GREEN),
            ft.Text("App Heatmap", size=30, weight=ft.FontWeight.BOLD),
            ft.Container(height=20),
            user_input,
            pass_input,
            ft.Button("Entrar", on_click=btn_login_click, width=300, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
        )
        page.update()

    show_login()

if __name__ == '__main__':
    ft.run(main)