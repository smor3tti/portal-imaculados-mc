"""
Portal Imaculados M.C. - Schemas Pydantic (entrada/saída da API)
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------- Auth ----------
class LoginRequest(BaseModel):
    login: str
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    cargo: str
    nome: str


# ---------- Integrante ----------
class IntegranteBase(BaseModel):
    nome: str
    apelido: Optional[str] = None
    cpf: Optional[str] = None
    rg: Optional[str] = None
    data_nascimento: Optional[date] = None
    cargo: str = "Integrante"
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    endereco: Optional[str] = None
    tipo_sanguineo: Optional[str] = None
    contato_emergencia: Optional[str] = None
    moto_modelo: Optional[str] = None
    moto_placa: Optional[str] = None
    status: str = "Ativo"


class IntegranteCreate(IntegranteBase):
    pass


class IntegranteOut(IntegranteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data_entrada: date


class IntegranteUpdate(BaseModel):
    nome: Optional[str] = None
    apelido: Optional[str] = None
    cpf: Optional[str] = None
    rg: Optional[str] = None
    data_nascimento: Optional[date] = None
    cargo: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    endereco: Optional[str] = None
    tipo_sanguineo: Optional[str] = None
    contato_emergencia: Optional[str] = None
    moto_modelo: Optional[str] = None
    moto_placa: Optional[str] = None
    status: Optional[str] = None


# ---------- Mensalidade ----------
class MensalidadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    integrante_id: int
    integrante_nome: Optional[str] = None
    referencia: str
    vencimento: date
    valor: Decimal
    pago: bool
    data_pagamento: Optional[date] = None
    forma_pagamento: Optional[str] = None


class MensalidadeCreate(BaseModel):
    integrante_id: int
    referencia: str  # "2026-08"
    vencimento: date
    valor: Decimal


class MensalidadePagamento(BaseModel):
    forma_pagamento: str
    data_pagamento: Optional[date] = None


# ---------- Dashboard ----------
class DashboardResumo(BaseModel):
    total_integrantes: int
    percentual_mensalidades_pagas: float
    saldo_caixa: Decimal
    proximo_evento_nome: Optional[str] = None
    proximo_evento_data: Optional[date] = None
