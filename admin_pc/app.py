"""
Portal Imaculados M.C. - Aplicativo Administrativo (Desktop)

Como rodar:
    1) Suba o backend primeiro (na pasta backend/):
         uvicorn main:app --reload
    2) Nesta pasta (admin_pc/):
         pip install PySide6 requests
         python app.py

Usuário de teste (criado via backend/criar_admin.py):
    login: presidente
    senha: imaculados123
"""
import os
import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from login import TelaLogin
from dashboard import TelaDashboard


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Portal Imaculados M.C.")
        self.resize(1080, 680)
        self.setMinimumSize(900, 560)

        self.pilha = QStackedWidget()
        self.setCentralWidget(self.pilha)

        self.tela_login = TelaLogin()
        self.tela_login.login_sucesso.connect(self._ao_logar)
        self.pilha.addWidget(self.tela_login)

    def _ao_logar(self, token: str, cargo: str, nome: str):
        tela_dashboard = TelaDashboard(token=token, cargo=cargo, nome=nome)
        self.pilha.addWidget(tela_dashboard)
        self.pilha.setCurrentWidget(tela_dashboard)


def carregar_estilo(app: QApplication):
    caminho_qss = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(caminho_qss):
        with open(caminho_qss, "r", encoding="utf-8") as arquivo:
            app.setStyleSheet(arquivo.read())


def main():
    app = QApplication(sys.argv)
    carregar_estilo(app)

    janela = JanelaPrincipal()
    janela.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
