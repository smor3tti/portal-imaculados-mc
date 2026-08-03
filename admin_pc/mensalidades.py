"""
Portal Imaculados M.C. - Controle de Mensalidades
"""
import os
from datetime import date

import requests
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QMessageBox, QInputDialog,
)

API_URL = os.getenv("PORTAL_API_URL", "http://127.0.0.1:8000")

FORMAS_PAGAMENTO = ["Pix", "Dinheiro", "Cartão", "Transferência"]


class PaginaMensalidades(QWidget):
    """Lista mensalidades, permite filtrar por pendentes e registrar pagamento."""

    COLUNAS = ["Integrante", "Referência", "Vencimento", "Valor", "Status"]

    def __init__(self, token: str):
        super().__init__()
        self.token = token
        self._montar_interface()
        self.carregar_mensalidades()

    def _montar_interface(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        topo = QHBoxLayout()

        self.checkbox_pendentes = QCheckBox("Mostrar apenas pendentes")
        self.checkbox_pendentes.stateChanged.connect(lambda _: self.carregar_mensalidades())
        topo.addWidget(self.checkbox_pendentes)

        topo.addStretch()

        botao_pagar = QPushButton("Registrar Pagamento")
        botao_pagar.setObjectName("BotaoEntrar")
        botao_pagar.setCursor(Qt.PointingHandCursor)
        botao_pagar.setFixedWidth(180)
        botao_pagar.clicked.connect(self._registrar_pagamento)
        topo.addWidget(botao_pagar)

        layout.addLayout(topo)

        self.tabela = QTableWidget(0, len(self.COLUNAS))
        self.tabela.setHorizontalHeaderLabels(self.COLUNAS)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.tabela)

    def carregar_mensalidades(self):
        parametros = {}
        if self.checkbox_pendentes.isChecked():
            parametros["apenas_pendentes"] = True

        try:
            resposta = requests.get(
                f"{API_URL}/mensalidades",
                params=parametros,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            QMessageBox.warning(self, "Erro", "Não foi possível conectar ao servidor.")
            return

        if resposta.status_code != 200:
            return

        self._mensalidades = resposta.json()
        self._preencher_tabela(self._mensalidades)

    def _preencher_tabela(self, mensalidades: list[dict]):
        self.tabela.setRowCount(0)
        for linha, mensalidade in enumerate(mensalidades):
            self.tabela.insertRow(linha)

            pago = mensalidade.get("pago")
            status_texto = "Pago" if pago else "Pendente"
            valor = mensalidade.get("valor", 0)

            valores = [
                mensalidade.get("integrante_nome") or f"#{mensalidade.get('integrante_id')}",
                mensalidade.get("referencia", ""),
                mensalidade.get("vencimento", ""),
                f"R$ {float(valor):,.2f}".replace(",", "."),
                status_texto,
            ]
            for coluna, valor_texto in enumerate(valores):
                item = QTableWidgetItem(valor_texto)
                if coluna == 4:
                    item.setForeground(QColor("#4caf50") if pago else QColor("#e2574c"))
                self.tabela.setItem(linha, coluna, item)

            # guarda o id real da mensalidade na primeira célula da linha
            self.tabela.item(linha, 0).setData(Qt.UserRole, mensalidade.get("id"))

    def _registrar_pagamento(self):
        linha_selecionada = self.tabela.currentRow()
        if linha_selecionada < 0:
            QMessageBox.information(self, "Selecione uma mensalidade",
                                     "Clique em uma linha da tabela primeiro.")
            return

        mensalidade_id = self.tabela.item(linha_selecionada, 0).data(Qt.UserRole)
        status_atual = self.tabela.item(linha_selecionada, 4).text()

        if status_atual == "Pago":
            QMessageBox.information(self, "Já paga", "Esta mensalidade já está registrada como paga.")
            return

        forma, ok = QInputDialog.getItem(
            self, "Forma de pagamento", "Como foi pago:", FORMAS_PAGAMENTO, editable=False
        )
        if not ok:
            return

        try:
            resposta = requests.patch(
                f"{API_URL}/mensalidades/{mensalidade_id}/pagar",
                json={"forma_pagamento": forma, "data_pagamento": date.today().isoformat()},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            QMessageBox.warning(self, "Erro", "Não foi possível conectar ao servidor.")
            return

        if resposta.status_code != 200:
            QMessageBox.warning(self, "Erro", "Não foi possível registrar o pagamento.")
            return

        self.carregar_mensalidades()
