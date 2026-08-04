"""
Portal Imaculados M.C. - Modelos do banco de dados
"""
from datetime import datetime, date

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime,
    Numeric, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from database import Base


class Usuario(Base):
    """Login de acesso ao sistema (vinculado a um Integrante)."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    integrante_id = Column(Integer, ForeignKey("integrantes.id"), unique=True)
    login = Column(String(50), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    cargo = Column(String(30), nullable=False, default="Integrante")
    # Cargos oficiais: Presidente, Vice-Presidente, Diretor, Tesoureiro, Disciplina, Integrante, Prospero
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    integrante = relationship("Integrante", back_populates="usuario")


class Integrante(Base):
    __tablename__ = "integrantes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    apelido = Column(String(80))
    cpf = Column(String(14), unique=True)
    rg = Column(String(20))
    data_nascimento = Column(Date)
    data_entrada = Column(Date, default=date.today)
    cargo = Column(String(30), default="Integrante")
    telefone = Column(String(20))
    whatsapp = Column(String(20))
    email = Column(String(120))
    endereco = Column(String(200))
    tipo_sanguineo = Column(String(5))
    contato_emergencia = Column(String(150))
    foto_path = Column(String(255))
    moto_modelo = Column(String(100))
    moto_placa = Column(String(10))
    status = Column(String(10), default="Ativo")  # Ativo / Inativo

    usuario = relationship("Usuario", back_populates="integrante", uselist=False)
    mensalidades = relationship("Mensalidade", back_populates="integrante")


class Mensalidade(Base):
    __tablename__ = "mensalidades"

    id = Column(Integer, primary_key=True, index=True)
    integrante_id = Column(Integer, ForeignKey("integrantes.id"), nullable=False)
    referencia = Column(String(7), nullable=False)  # "2026-08"
    vencimento = Column(Date, nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    pago = Column(Boolean, default=False)
    data_pagamento = Column(Date, nullable=True)
    forma_pagamento = Column(String(30), nullable=True)  # Pix, Dinheiro, Cartão...
    observacoes = Column(Text, nullable=True)

    integrante = relationship("Integrante", back_populates="mensalidades")


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    data = Column(Date, nullable=False)
    local = Column(String(200))
    descricao = Column(Text)
    tipo = Column(String(20), default="Encontro")  # Passeio, Encontro, Churrasco, Aniversário, Outro
    status = Column(String(20), default="Planejado")  # Planejado, Confirmado, Realizado, Cancelado
    criador_id = Column(Integer, ForeignKey("integrantes.id"), nullable=True)

    presencas = relationship("Presenca", back_populates="evento", cascade="all, delete-orphan")


class Presenca(Base):
    __tablename__ = "presencas"

    id = Column(Integer, primary_key=True, index=True)
    evento_id = Column(Integer, ForeignKey("eventos.id"), nullable=False)
    integrante_id = Column(Integer, ForeignKey("integrantes.id"), nullable=False)
    confirmacao = Column(String(15), default="Pendente")  # Pendente, Confirmado, Recusado

    evento = relationship("Evento", back_populates="presencas")
    integrante = relationship("Integrante")


class Caixa(Base):
    """Lançamentos financeiros gerais (entradas e saídas)."""
    __tablename__ = "caixa"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(10), nullable=False)  # Entrada / Saída
    descricao = Column(String(200), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    data = Column(Date, default=date.today)
