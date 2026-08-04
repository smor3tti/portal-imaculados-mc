"""
Portal Imaculados M.C. - Schemas Pydantic (entrada/saída da API)
"""
from datetime import date, datetime
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
    valor: Decimal = Decimal("40.00")  # valor padrão da mensalidade do clube


class MensalidadePagamento(BaseModel):
    forma_pagamento: str
    data_pagamento: Optional[date] = None


# ---------- Eventos ----------
class EventoBase(BaseModel):
    nome: str
    data: date
    local: Optional[str] = None
    descricao: Optional[str] = None
    tipo: str = "Encontro"  # Passeio, Encontro, Churrasco, Aniversário, Outro
    status: str = "Planejado"  # Planejado, Confirmado, Realizado, Cancelado


class EventoCreate(EventoBase):
    pass


class EventoUpdate(BaseModel):
    nome: Optional[str] = None
    data: Optional[date] = None
    local: Optional[str] = None
    descricao: Optional[str] = None
    tipo: Optional[str] = None
    status: Optional[str] = None


class EventoOut(EventoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    criador_id: Optional[int] = None
    total_confirmados: int = 0


# ---------- Presenças ----------
class PresencaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    evento_id: int
    integrante_id: int
    integrante_nome: Optional[str] = None
    confirmacao: str


class PresencaAtualizar(BaseModel):
    confirmacao: str  # Confirmado, Recusado, Pendente


# ---------- Comunicados ----------
class ComunicadoBase(BaseModel):
    titulo: str
    mensagem: str
    fixado: bool = False


class ComunicadoCreate(ComunicadoBase):
    pass


class ComunicadoUpdate(BaseModel):
    titulo: Optional[str] = None
    mensagem: Optional[str] = None
    fixado: Optional[bool] = None


class ComunicadoOut(ComunicadoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data: datetime
    autor_id: Optional[int] = None
    autor_nome: Optional[str] = None


# ---------- Documentos ----------
class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    titulo: str
    categoria: str
    arquivo_nome: str
    tamanho_kb: int
    data_upload: datetime
    integrante_id: Optional[int] = None
    integrante_nome: Optional[str] = None


# ---------- Dashboard ----------
class AniversarianteResumo(BaseModel):
    id: int
    nome: str
    apelido: Optional[str] = None
    data_nascimento: date


class ComunicadoResumo(BaseModel):
    id: int
    titulo: str
    data: datetime
    autor_nome: Optional[str] = None


class DashboardResumo(BaseModel):
    total_integrantes: int
    percentual_mensalidades_pagas: float
    saldo_caixa: Decimal
    proximo_evento_nome: Optional[str] = None
    proximo_evento_data: Optional[date] = None
    aniversariantes_mes: list[AniversarianteResumo] = []
    ultimos_comunicados: list[ComunicadoResumo] = []
