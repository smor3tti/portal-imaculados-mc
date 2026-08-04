"""
Portal Imaculados M.C. - API principal (FastAPI)

Rodar em desenvolvimento:
    uvicorn main:app --reload
"""
from datetime import date
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db, init_db

app = FastAPI(title="Portal Imaculados M.C. API", version="0.1.0")

# Cargos oficiais do clube e valor padrão da mensalidade
CARGOS_VALIDOS = ["Presidente", "Vice-Presidente", "Diretor", "Tesoureiro", "Disciplina", "Integrante", "Prospero"]
VALOR_MENSALIDADE_PADRAO = Decimal("40.00")

# Libera acesso do app desktop / futuro PWA. Em produção, restrinja allow_origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def raiz():
    return {"status": "online", "sistema": "Portal Imaculados M.C."}


# ---------- Autenticação ----------
@app.post("/auth/login", response_model=schemas.Token)
def login(dados: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = auth.autenticar_usuario(db, dados.login, dados.senha)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    token = auth.criar_access_token({"sub": str(usuario.id)})
    nome = usuario.integrante.nome if usuario.integrante else usuario.login
    return schemas.Token(access_token=token, cargo=usuario.cargo, nome=nome)


# ---------- Dashboard ----------
@app.get("/dashboard", response_model=schemas.DashboardResumo)
def resumo_dashboard(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    total_integrantes = (
        db.query(models.Integrante)
        .filter(models.Integrante.status == "Ativo")
        .count()
    )

    total_mensalidades = db.query(models.Mensalidade).count()
    pagas = db.query(models.Mensalidade).filter(models.Mensalidade.pago.is_(True)).count()
    percentual = (pagas / total_mensalidades * 100) if total_mensalidades else 0.0

    entradas = db.query(func.coalesce(func.sum(models.Caixa.valor), 0)).filter(
        models.Caixa.tipo == "Entrada"
    ).scalar()
    saidas = db.query(func.coalesce(func.sum(models.Caixa.valor), 0)).filter(
        models.Caixa.tipo == "Saída"
    ).scalar()
    saldo = Decimal(entradas or 0) - Decimal(saidas or 0)

    proximo_evento = (
        db.query(models.Evento)
        .filter(models.Evento.data >= date.today())
        .order_by(models.Evento.data.asc())
        .first()
    )

    mes_atual = date.today().month
    aniversariantes = (
        db.query(models.Integrante)
        .filter(models.Integrante.status == "Ativo")
        .filter(models.Integrante.data_nascimento.isnot(None))
        .filter(func.extract("month", models.Integrante.data_nascimento) == mes_atual)
        .all()
    )

    ultimos_comunicados = (
        db.query(models.Comunicado)
        .order_by(models.Comunicado.fixado.desc(), models.Comunicado.data.desc())
        .limit(3)
        .all()
    )

    return schemas.DashboardResumo(
        total_integrantes=total_integrantes,
        percentual_mensalidades_pagas=round(percentual, 1),
        saldo_caixa=saldo,
        proximo_evento_nome=proximo_evento.nome if proximo_evento else None,
        proximo_evento_data=proximo_evento.data if proximo_evento else None,
        aniversariantes_mes=[
            schemas.AniversarianteResumo(
                id=i.id, nome=i.nome, apelido=i.apelido, data_nascimento=i.data_nascimento
            )
            for i in aniversariantes
        ],
        ultimos_comunicados=[
            schemas.ComunicadoResumo(
                id=c.id, titulo=c.titulo, data=c.data,
                autor_nome=c.autor.nome if c.autor else None,
            )
            for c in ultimos_comunicados
        ],
    )


# ---------- Integrantes (CRUD básico) ----------
@app.get("/integrantes", response_model=list[schemas.IntegranteOut])
def listar_integrantes(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    return db.query(models.Integrante).order_by(models.Integrante.nome).all()


@app.post("/integrantes", response_model=schemas.IntegranteOut)
def criar_integrante(
    dados: schemas.IntegranteCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor")),
):
    novo = models.Integrante(**dados.model_dump())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@app.put("/integrantes/{integrante_id}", response_model=schemas.IntegranteOut)
def atualizar_integrante(
    integrante_id: int,
    dados: schemas.IntegranteUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor")),
):
    integrante = db.query(models.Integrante).filter(models.Integrante.id == integrante_id).first()
    if not integrante:
        raise HTTPException(status_code=404, detail="Integrante não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(integrante, campo, valor)

    db.commit()
    db.refresh(integrante)
    return integrante


@app.delete("/integrantes/{integrante_id}")
def excluir_integrante(
    integrante_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Tesoureiro")),
):
    integrante = db.query(models.Integrante).filter(models.Integrante.id == integrante_id).first()
    if not integrante:
        raise HTTPException(status_code=404, detail="Integrante não encontrado")

    db.delete(integrante)
    db.commit()
    return {"detail": "Integrante excluído"}


# ---------- Mensalidades ----------
@app.get("/mensalidades", response_model=list[schemas.MensalidadeOut])
def listar_mensalidades(
    integrante_id: int | None = None,
    referencia: str | None = None,
    apenas_pendentes: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    consulta = db.query(models.Mensalidade)
    if integrante_id is not None:
        consulta = consulta.filter(models.Mensalidade.integrante_id == integrante_id)
    if referencia is not None:
        consulta = consulta.filter(models.Mensalidade.referencia == referencia)
    if apenas_pendentes:
        consulta = consulta.filter(models.Mensalidade.pago.is_(False))

    mensalidades = consulta.order_by(models.Mensalidade.vencimento.desc()).all()

    resultado = []
    for mensalidade in mensalidades:
        item = schemas.MensalidadeOut.model_validate(mensalidade)
        item.integrante_nome = mensalidade.integrante.nome if mensalidade.integrante else None
        resultado.append(item)
    return resultado


@app.post("/mensalidades", response_model=schemas.MensalidadeOut)
def criar_mensalidade(
    dados: schemas.MensalidadeCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Tesoureiro")),
):
    integrante = db.query(models.Integrante).filter(
        models.Integrante.id == dados.integrante_id
    ).first()
    if not integrante:
        raise HTTPException(status_code=404, detail="Integrante não encontrado")

    nova = models.Mensalidade(**dados.model_dump())
    db.add(nova)
    db.commit()
    db.refresh(nova)

    item = schemas.MensalidadeOut.model_validate(nova)
    item.integrante_nome = integrante.nome
    return item


@app.patch("/mensalidades/{mensalidade_id}/pagar", response_model=schemas.MensalidadeOut)
def registrar_pagamento(
    mensalidade_id: int,
    dados: schemas.MensalidadePagamento,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Tesoureiro")),
):
    mensalidade = db.query(models.Mensalidade).filter(
        models.Mensalidade.id == mensalidade_id
    ).first()
    if not mensalidade:
        raise HTTPException(status_code=404, detail="Mensalidade não encontrada")

    mensalidade.pago = True
    mensalidade.forma_pagamento = dados.forma_pagamento
    mensalidade.data_pagamento = dados.data_pagamento or date.today()

    # Lança automaticamente a entrada no caixa
    lancamento = models.Caixa(
        tipo="Entrada",
        descricao=f"Mensalidade {mensalidade.referencia} - {mensalidade.integrante.nome}",
        valor=mensalidade.valor,
        data=mensalidade.data_pagamento,
    )
    db.add(lancamento)

    db.commit()
    db.refresh(mensalidade)

    item = schemas.MensalidadeOut.model_validate(mensalidade)
    item.integrante_nome = mensalidade.integrante.nome if mensalidade.integrante else None
    return item


# ---------- Eventos ----------
def _evento_para_out(evento: models.Evento) -> schemas.EventoOut:
    item = schemas.EventoOut.model_validate(evento)
    item.total_confirmados = sum(1 for p in evento.presencas if p.confirmacao == "Confirmado")
    return item


@app.get("/eventos", response_model=list[schemas.EventoOut])
def listar_eventos(
    apenas_futuros: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    consulta = db.query(models.Evento)
    if apenas_futuros:
        consulta = consulta.filter(models.Evento.data >= date.today())
    eventos = consulta.order_by(models.Evento.data.asc()).all()
    return [_evento_para_out(e) for e in eventos]


@app.post("/eventos", response_model=schemas.EventoOut)
def criar_evento(
    dados: schemas.EventoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor")),
):
    novo = models.Evento(**dados.model_dump(), criador_id=usuario.integrante_id)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return _evento_para_out(novo)


@app.put("/eventos/{evento_id}", response_model=schemas.EventoOut)
def atualizar_evento(
    evento_id: int,
    dados: schemas.EventoUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor")),
):
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(evento, campo, valor)

    db.commit()
    db.refresh(evento)
    return _evento_para_out(evento)


@app.delete("/eventos/{evento_id}")
def excluir_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor")),
):
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    db.delete(evento)
    db.commit()
    return {"detail": "Evento excluído"}


# ---------- Presenças ----------
@app.get("/eventos/{evento_id}/presencas", response_model=list[schemas.PresencaOut])
def listar_presencas(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    resultado = []
    for p in evento.presencas:
        item = schemas.PresencaOut.model_validate(p)
        item.integrante_nome = p.integrante.nome if p.integrante else None
        resultado.append(item)
    return resultado


@app.post("/eventos/{evento_id}/presenca", response_model=schemas.PresencaOut)
def confirmar_presenca(
    evento_id: int,
    dados: schemas.PresencaAtualizar,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    """Confirma/atualiza a presença do próprio usuário autenticado em um evento."""
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if not usuario.integrante_id:
        raise HTTPException(status_code=400, detail="Usuário não vinculado a um integrante")

    presenca = (
        db.query(models.Presenca)
        .filter(
            models.Presenca.evento_id == evento_id,
            models.Presenca.integrante_id == usuario.integrante_id,
        )
        .first()
    )
    if presenca:
        presenca.confirmacao = dados.confirmacao
    else:
        presenca = models.Presenca(
            evento_id=evento_id,
            integrante_id=usuario.integrante_id,
            confirmacao=dados.confirmacao,
        )
        db.add(presenca)

    db.commit()
    db.refresh(presenca)

    item = schemas.PresencaOut.model_validate(presenca)
    item.integrante_nome = presenca.integrante.nome if presenca.integrante else None
    return item


# ---------- Comunicados ----------
def _comunicado_para_out(c: models.Comunicado) -> schemas.ComunicadoOut:
    item = schemas.ComunicadoOut.model_validate(c)
    item.autor_nome = c.autor.nome if c.autor else None
    return item


@app.get("/comunicados", response_model=list[schemas.ComunicadoOut])
def listar_comunicados(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.obter_usuario_atual),
):
    comunicados = (
        db.query(models.Comunicado)
        .order_by(models.Comunicado.fixado.desc(), models.Comunicado.data.desc())
        .all()
    )
    return [_comunicado_para_out(c) for c in comunicados]


@app.post("/comunicados", response_model=schemas.ComunicadoOut)
def criar_comunicado(
    dados: schemas.ComunicadoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(
        auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor", "Disciplina")
    ),
):
    novo = models.Comunicado(**dados.model_dump(), autor_id=usuario.integrante_id)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return _comunicado_para_out(novo)


@app.put("/comunicados/{comunicado_id}", response_model=schemas.ComunicadoOut)
def atualizar_comunicado(
    comunicado_id: int,
    dados: schemas.ComunicadoUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(
        auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor", "Disciplina")
    ),
):
    comunicado = db.query(models.Comunicado).filter(models.Comunicado.id == comunicado_id).first()
    if not comunicado:
        raise HTTPException(status_code=404, detail="Comunicado não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(comunicado, campo, valor)

    db.commit()
    db.refresh(comunicado)
    return _comunicado_para_out(comunicado)


@app.delete("/comunicados/{comunicado_id}")
def excluir_comunicado(
    comunicado_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(
        auth.exigir_cargo("Presidente", "Vice-Presidente", "Diretor", "Disciplina")
    ),
):
    comunicado = db.query(models.Comunicado).filter(models.Comunicado.id == comunicado_id).first()
    if not comunicado:
        raise HTTPException(status_code=404, detail="Comunicado não encontrado")

    db.delete(comunicado)
    db.commit()
    return {"detail": "Comunicado excluído"}
