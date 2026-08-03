"""
Portal Imaculados M.C. - Tela principal pós-login (sidebar + páginas)
"""
import os

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QButtonGroup, QStackedWidget,
)

from membros import PaginaIntegrantes
from mensalidades import PaginaMensalidades

API_URL = os.getenv("PORTAL_API_URL", "http://127.0.0.1:8000")

# texto do menu -> índice fixo na pilha de páginas
MENU_ITENS = ["Dashboard", "Integrantes", "Mensalidades", "Caixa", "Eventos", "Relatórios"]


def _criar_card(titulo: str, valor: str) -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    card.setMinimumHeight(100)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)

    label_titulo = QLabel(titulo.upper())
    label_titulo.setObjectName("CardTitulo")
    layout.addWidget(label_titulo)

    label_valor = QLabel(valor)
    label_valor.setObjectName("CardValor")
    layout.addWidget(label_valor)

    layout.addStretch()
    return card


class PaginaEmConstrucao(QWidget):
    """Placeholder para módulos ainda não implementados (Caixa, Eventos, Relatórios)."""

    def __init__(self, nome_modulo: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(f'Módulo "{nome_modulo}" — em construção')
        label.setObjectName("CardTitulo")
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)


class PaginaDashboard(QWidget):
    """Cards de resumo (integrantes, mensalidades, caixa, próximo evento)."""

    def __init__(self, token: str):
        super().__init__()
        self.token = token
        layout = QHBoxLayout(self)
        layout.setSpacing(16)

        self.card_integrantes = _criar_card("Integrantes", "—")
        self.card_mensalidades = _criar_card("Mensalidades pagas", "—")
        self.card_caixa = _criar_card("Saldo em caixa", "—")
        self.card_evento = _criar_card("Próximo evento", "—")

        for card in (self.card_integrantes, self.card_mensalidades,
                     self.card_caixa, self.card_evento):
            layout.addWidget(card)

        self.carregar_resumo()

    def carregar_resumo(self):
        try:
            resposta = requests.get(
                f"{API_URL}/dashboard",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            return

        if resposta.status_code != 200:
            return

        dados = resposta.json()
        self._atualizar_valor_card(self.card_integrantes, str(dados["total_integrantes"]))
        self._atualizar_valor_card(
            self.card_mensalidades, f"{dados['percentual_mensalidades_pagas']:.0f}%"
        )
        self._atualizar_valor_card(
            self.card_caixa, f"R$ {dados['saldo_caixa']:,.2f}".replace(",", ".")
        )
        evento_nome = dados.get("proximo_evento_nome") or "Nenhum agendado"
        self._atualizar_valor_card(self.card_evento, evento_nome)

    @staticmethod
    def _atualizar_valor_card(card: QFrame, novo_valor: str):
        label_valor = card.findChild(QLabel, "CardValor")
        if label_valor:
            label_valor.setText(novo_valor)


class TelaDashboard(QWidget):
    """Casca principal pós-login: sidebar de navegação + páginas do sistema."""

    def __init__(self, token: str, cargo: str, nome: str):
        super().__init__()
        self.token = token
        self.cargo = cargo
        self.nome = nome
        self._montar_interface()

    def _montar_interface(self):
        layout_geral = QHBoxLayout(self)
        layout_geral.setContentsMargins(0, 0, 0, 0)
        layout_geral.setSpacing(0)

        layout_geral.addWidget(self._montar_sidebar())

        area_direita = QVBoxLayout()
        area_direita.setContentsMargins(28, 24, 28, 24)
        area_direita.setSpacing(20)

        self.label_saudacao = QLabel(f"Olá, {self.cargo}")
        self.label_saudacao.setObjectName("SaudacaoTopo")
        area_direita.addWidget(self.label_saudacao)

        self.stack = QStackedWidget()
        self._pagina_dashboard = PaginaDashboard(self.token)
        self._pagina_integrantes = PaginaIntegrantes(self.token)
        self._pagina_mensalidades = PaginaMensalidades(self.token)

        self.stack.addWidget(self._pagina_dashboard)      # índice 0
        self.stack.addWidget(self._pagina_integrantes)    # índice 1
        self.stack.addWidget(self._pagina_mensalidades)   # índice 2
        self.stack.addWidget(PaginaEmConstrucao("Caixa"))       # índice 3
        self.stack.addWidget(PaginaEmConstrucao("Eventos"))     # índice 4
        self.stack.addWidget(PaginaEmConstrucao("Relatórios"))  # índice 5

        area_direita.addWidget(self.stack)

        container_direita = QWidget()
        container_direita.setLayout(area_direita)
        layout_geral.addWidget(container_direita, stretch=1)

    def _montar_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(4)

        titulo = QLabel("IMACULADOS\nM.C.")
        titulo.setObjectName("TituloClube")
        titulo.setStyleSheet("font-size: 15px;")
        layout.addWidget(titulo)
        layout.addSpacing(20)

        self.grupo_botoes = QButtonGroup(self)
        self.grupo_botoes.setExclusive(True)

        for indice, texto in enumerate(MENU_ITENS):
            botao = QPushButton(texto)
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            self.grupo_botoes.addButton(botao, indice)
            layout.addWidget(botao)

        self.grupo_botoes.idClicked.connect(self._trocar_pagina)
        self.grupo_botoes.buttons()[0].setChecked(True)

        layout.addStretch()
        return sidebar

    def _trocar_pagina(self, indice: int):
        self.stack.setCurrentIndex(indice)

        # recarrega dados da página ao entrar nela
        pagina_atual = self.stack.currentWidget()
        if hasattr(pagina_atual, "carregar_resumo"):
            pagina_atual.carregar_resumo()
        elif hasattr(pagina_atual, "carregar_integrantes"):
            pagina_atual.carregar_integrantes()
        elif hasattr(pagina_atual, "carregar_mensalidades"):
            pagina_atual.carregar_mensalidades()
