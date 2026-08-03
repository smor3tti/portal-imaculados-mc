"""
Portal Imaculados M.C. - Cadastro de Membros
"""
import os

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QComboBox, QDateEdit, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import QDate

API_URL = os.getenv("PORTAL_API_URL", "http://127.0.0.1:8000")

CARGOS = ["Presidente", "Vice", "Diretor", "Tesoureiro", "Secretário", "Integrante"]


class DialogoIntegrante(QDialog):
    """Formulário de cadastro de um novo integrante."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo Integrante")
        self.setMinimumWidth(380)
        self._montar_formulario()

    def _montar_formulario(self):
        layout = QFormLayout(self)

        self.campo_nome = QLineEdit()
        self.campo_apelido = QLineEdit()
        self.campo_cpf = QLineEdit()
        self.campo_telefone = QLineEdit()
        self.campo_whatsapp = QLineEdit()
        self.campo_email = QLineEdit()
        self.campo_moto = QLineEdit()
        self.campo_placa = QLineEdit()

        self.combo_cargo = QComboBox()
        self.combo_cargo.addItems(CARGOS)

        self.data_nascimento = QDateEdit()
        self.data_nascimento.setCalendarPopup(True)
        self.data_nascimento.setDate(QDate(1990, 1, 1))

        layout.addRow("Nome*:", self.campo_nome)
        layout.addRow("Apelido:", self.campo_apelido)
        layout.addRow("CPF:", self.campo_cpf)
        layout.addRow("Nascimento:", self.data_nascimento)
        layout.addRow("Cargo:", self.combo_cargo)
        layout.addRow("Telefone:", self.campo_telefone)
        layout.addRow("WhatsApp:", self.campo_whatsapp)
        layout.addRow("E-mail:", self.campo_email)
        layout.addRow("Moto (modelo):", self.campo_moto)
        layout.addRow("Placa:", self.campo_placa)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar_e_aceitar)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

    def _validar_e_aceitar(self):
        if not self.campo_nome.text().strip():
            QMessageBox.warning(self, "Campo obrigatório", "Informe o nome do integrante.")
            return
        self.accept()

    def dados(self) -> dict:
        return {
            "nome": self.campo_nome.text().strip(),
            "apelido": self.campo_apelido.text().strip() or None,
            "cpf": self.campo_cpf.text().strip() or None,
            "data_nascimento": self.data_nascimento.date().toString("yyyy-MM-dd"),
            "cargo": self.combo_cargo.currentText(),
            "telefone": self.campo_telefone.text().strip() or None,
            "whatsapp": self.campo_whatsapp.text().strip() or None,
            "email": self.campo_email.text().strip() or None,
            "moto_modelo": self.campo_moto.text().strip() or None,
            "moto_placa": self.campo_placa.text().strip() or None,
            "status": "Ativo",
        }


class PaginaIntegrantes(QWidget):
    """Lista os integrantes cadastrados e permite adicionar novos."""

    COLUNAS = ["Nome", "Apelido", "Cargo", "Telefone", "Status"]

    def __init__(self, token: str):
        super().__init__()
        self.token = token
        self._montar_interface()
        self.carregar_integrantes()

    def _montar_interface(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        topo = QHBoxLayout()
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar por nome ou apelido...")
        self.campo_busca.textChanged.connect(self._filtrar)
        topo.addWidget(self.campo_busca)

        botao_novo = QPushButton("+ Novo Integrante")
        botao_novo.setObjectName("BotaoEntrar")
        botao_novo.setCursor(Qt.PointingHandCursor)
        botao_novo.setFixedWidth(160)
        botao_novo.clicked.connect(self._abrir_dialogo_novo)
        topo.addWidget(botao_novo)

        layout.addLayout(topo)

        self.tabela = QTableWidget(0, len(self.COLUNAS))
        self.tabela.setHorizontalHeaderLabels(self.COLUNAS)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.tabela)

    def carregar_integrantes(self):
        try:
            resposta = requests.get(
                f"{API_URL}/integrantes",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            QMessageBox.warning(self, "Erro", "Não foi possível conectar ao servidor.")
            return

        if resposta.status_code != 200:
            return

        self._integrantes = resposta.json()
        self._preencher_tabela(self._integrantes)

    def _preencher_tabela(self, integrantes: list[dict]):
        self.tabela.setRowCount(0)
        for linha, integrante in enumerate(integrantes):
            self.tabela.insertRow(linha)
            valores = [
                integrante.get("nome", ""),
                integrante.get("apelido") or "",
                integrante.get("cargo", ""),
                integrante.get("telefone") or "",
                integrante.get("status", ""),
            ]
            for coluna, valor in enumerate(valores):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(valor))

    def _filtrar(self, texto: str):
        texto = texto.lower().strip()
        if not hasattr(self, "_integrantes"):
            return
        if not texto:
            self._preencher_tabela(self._integrantes)
            return
        filtrados = [
            i for i in self._integrantes
            if texto in i.get("nome", "").lower() or texto in (i.get("apelido") or "").lower()
        ]
        self._preencher_tabela(filtrados)

    def _abrir_dialogo_novo(self):
        dialogo = DialogoIntegrante(self)
        if dialogo.exec() != QDialog.Accepted:
            return

        try:
            resposta = requests.post(
                f"{API_URL}/integrantes",
                json=dialogo.dados(),
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            QMessageBox.warning(self, "Erro", "Não foi possível conectar ao servidor.")
            return

        if resposta.status_code not in (200, 201):
            QMessageBox.warning(self, "Erro", "Não foi possível cadastrar o integrante.")
            return

        self.carregar_integrantes()
