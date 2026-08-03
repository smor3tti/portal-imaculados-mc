"""
Portal Imaculados M.C. - Tela de Login
"""
import os

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy,
)

API_URL = os.getenv("PORTAL_API_URL", "http://127.0.0.1:8000")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


class TelaLogin(QWidget):
    """Tela inicial de autenticação. Emite `login_sucesso` com (token, cargo, nome)."""

    login_sucesso = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self._montar_interface()

    def _montar_interface(self):
        layout_geral = QVBoxLayout(self)
        layout_geral.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(14)

        # Brasão
        brasao_label = QLabel()
        brasao_path = os.path.join(ASSETS_DIR, "brasao.png")
        if os.path.exists(brasao_path):
            pixmap = QPixmap(brasao_path).scaledToWidth(140, Qt.SmoothTransformation)
            brasao_label.setPixmap(pixmap)
        brasao_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(brasao_label)

        titulo = QLabel("IMACULADOS MOTOR CLUBE")
        titulo.setObjectName("TituloClube")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setWordWrap(True)
        card_layout.addWidget(titulo)

        subtitulo = QLabel("Portal Administrativo")
        subtitulo.setObjectName("SubtituloLogin")
        subtitulo.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitulo)

        card_layout.addSpacing(10)

        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("Usuário")
        card_layout.addWidget(self.campo_usuario)

        self.campo_senha = QLineEdit()
        self.campo_senha.setPlaceholderText("Senha")
        self.campo_senha.setEchoMode(QLineEdit.Password)
        self.campo_senha.returnPressed.connect(self._entrar)
        card_layout.addWidget(self.campo_senha)

        self.label_erro = QLabel("")
        self.label_erro.setObjectName("LabelErro")
        self.label_erro.setAlignment(Qt.AlignCenter)
        self.label_erro.setWordWrap(True)
        card_layout.addWidget(self.label_erro)

        botao_entrar = QPushButton("ENTRAR")
        botao_entrar.setObjectName("BotaoEntrar")
        botao_entrar.setCursor(Qt.PointingHandCursor)
        botao_entrar.clicked.connect(self._entrar)
        card_layout.addWidget(botao_entrar)

        layout_geral.addWidget(card)

    def _entrar(self):
        login = self.campo_usuario.text().strip()
        senha = self.campo_senha.text()

        if not login or not senha:
            self.label_erro.setText("Preencha usuário e senha.")
            return

        try:
            resposta = requests.post(
                f"{API_URL}/auth/login",
                json={"login": login, "senha": senha},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            self.label_erro.setText("Não foi possível conectar ao servidor.")
            return

        if resposta.status_code != 200:
            self.label_erro.setText("Usuário ou senha inválidos.")
            return

        dados = resposta.json()
        self.label_erro.setText("")
        self.login_sucesso.emit(dados["access_token"], dados["cargo"], dados["nome"])
