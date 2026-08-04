"""
Portal Imaculados M.C. - API principal (FastAPI)

Rodar em desenvolvimento:
    uvicorn main:app --reload
"""
import os
import re
import secrets
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
import models
import permissoes
import schemas
from database import get_db, init_db

app = FastAPI(title="Portal Imaculados M.C. API", version="0.1.0")

# Cargos oficiais do clube e valor padrão da mensalidade
CARGOS_VALIDOS = ["Presidente", "Vice-Presidente", "Diretor", "Tesoureiro", "Disciplina", "Integrante", "Prospero"]
VALOR_MENSALIDADE_PADRAO = Decimal("40.00")

# Pasta local onde os arquivos enviados (atas, contratos etc.) são armazenados
PASTA_UPLOADS = Path(__file__).parent / "uploads"
PASTA_UPLOADS.mkdir(exist_ok=True)
TAMANHO_MAXIMO_MB = 15

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
    return schemas.Token(
        access_token=token,
        cargo=usuario.cargo,
        nome=nome,
        permissoes=sorted(auth.permissoes_do_usuario(usuario)),
    )


# ---------- Dashboard ----------
@app.get("/dashboard", response_model=schemas.DashboardResumo)
def resumo_dashboard(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_dashboard")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_integrantes")),
):
    return db.query(models.Integrante).order_by(models.Integrante.nome).all()


@app.post("/integrantes", response_model=schemas.IntegranteOut)
def criar_integrante(
    dados: schemas.IntegranteCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_integrantes")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_integrantes")),
):
    integrante = db.query(models.Integrante).filter(models.Integrante.id == integrante_id).first()
    if not integrante:
        raise HTTPException(status_code=404, detail="Integrante não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(integrante, campo, valor)

    # O cargo controla as permissões: espelha no usuário para não dessincronizar
    if dados.cargo is not None and integrante.usuario:
        if dados.cargo not in permissoes.CARGOS:
            raise HTTPException(status_code=400, detail="Cargo inválido")
        integrante.usuario.cargo = dados.cargo

    db.commit()
    db.refresh(integrante)
    return integrante


@app.delete("/integrantes/{integrante_id}")
def excluir_integrante(
    integrante_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("excluir_integrantes")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_financeiro")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_financeiro")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_financeiro")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_eventos")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_eventos")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_eventos")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("editar_eventos")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_eventos")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_eventos")),
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
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_comunicados")),
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
        auth.exigir_permissao("editar_comunicados")
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
        auth.exigir_permissao("editar_comunicados")
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
        auth.exigir_permissao("editar_comunicados")
    ),
):
    comunicado = db.query(models.Comunicado).filter(models.Comunicado.id == comunicado_id).first()
    if not comunicado:
        raise HTTPException(status_code=404, detail="Comunicado não encontrado")

    db.delete(comunicado)
    db.commit()
    return {"detail": "Comunicado excluído"}


# ---------- Documentos ----------
EXTENSOES_PERMITIDAS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xlsx", ".txt"}


def _documento_para_out(doc: models.Documento) -> schemas.DocumentoOut:
    item = schemas.DocumentoOut.model_validate(doc)
    item.integrante_nome = doc.integrante.nome if doc.integrante else None
    return item


@app.get("/documentos", response_model=list[schemas.DocumentoOut])
def listar_documentos(
    categoria: str | None = None,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_documentos")),
):
    consulta = db.query(models.Documento)
    if categoria:
        consulta = consulta.filter(models.Documento.categoria == categoria)
    documentos = consulta.order_by(models.Documento.data_upload.desc()).all()
    return [_documento_para_out(d) for d in documentos]


@app.post("/documentos", response_model=schemas.DocumentoOut)
async def enviar_documento(
    titulo: str = Form(...),
    categoria: str = Form("Outro"),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(
        auth.exigir_permissao("editar_documentos")
    ),
):
    extensao = Path(arquivo.filename).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não permitido. Use: {', '.join(sorted(EXTENSOES_PERMITIDAS))}",
        )

    conteudo = await arquivo.read()
    tamanho_kb = len(conteudo) // 1024
    if tamanho_kb > TAMANHO_MAXIMO_MB * 1024:
        raise HTTPException(status_code=400, detail=f"Arquivo maior que {TAMANHO_MAXIMO_MB}MB")

    nome_armazenado = f"{uuid.uuid4().hex}{extensao}"
    caminho_destino = PASTA_UPLOADS / nome_armazenado
    with open(caminho_destino, "wb") as f:
        f.write(conteudo)

    novo = models.Documento(
        titulo=titulo,
        categoria=categoria,
        arquivo_nome=arquivo.filename,
        arquivo_path=nome_armazenado,
        tamanho_kb=tamanho_kb,
        integrante_id=usuario.integrante_id,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return _documento_para_out(novo)


@app.get("/documentos/{documento_id}/download")
def baixar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_documentos")),
):
    documento = db.query(models.Documento).filter(models.Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    caminho = PASTA_UPLOADS / documento.arquivo_path
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor")

    return FileResponse(path=caminho, filename=documento.arquivo_nome)


@app.delete("/documentos/{documento_id}")
def excluir_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(
        auth.exigir_permissao("editar_documentos")
    ),
):
    documento = db.query(models.Documento).filter(models.Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    caminho = PASTA_UPLOADS / documento.arquivo_path
    if caminho.exists():
        os.remove(caminho)

    db.delete(documento)
    db.commit()
    return {"detail": "Documento excluído"}


# ---------- Solicitações de cadastro (site público) ----------
def _gerar_login(nome: str, db: Session) -> str:
    """Gera um login único a partir do nome (primeiro + último nome, sem acentos)."""
    normalizado = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    partes = re.sub(r"[^a-zA-Z ]", "", normalizado).lower().split()
    base = (partes[0] + (partes[-1] if len(partes) > 1 else "")) or "integrante"

    login = base
    contador = 1
    while db.query(models.Usuario).filter(models.Usuario.login == login).first():
        contador += 1
        login = f"{base}{contador}"
    return login


@app.post("/solicitacoes", response_model=schemas.SolicitacaoOut)
def enviar_solicitacao(dados: schemas.SolicitacaoCreate, db: Session = Depends(get_db)):
    """Endpoint público (sem autenticação) — formulário de ingresso no site."""
    nova = models.SolicitacaoCadastro(**dados.model_dump())
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


@app.get("/solicitacoes", response_model=list[schemas.SolicitacaoOut])
def listar_solicitacoes(
    status_filtro: str | None = None,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("ver_solicitacoes")),
):
    consulta = db.query(models.SolicitacaoCadastro)
    if status_filtro:
        consulta = consulta.filter(models.SolicitacaoCadastro.status == status_filtro)
    return consulta.order_by(models.SolicitacaoCadastro.data_solicitacao.desc()).all()


@app.post("/solicitacoes/{solicitacao_id}/aprovar", response_model=schemas.SolicitacaoAprovarOut)
def aprovar_solicitacao(
    solicitacao_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("analisar_solicitacoes")),
):
    solicitacao = db.query(models.SolicitacaoCadastro).filter(
        models.SolicitacaoCadastro.id == solicitacao_id
    ).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    if solicitacao.status != "Pendente":
        raise HTTPException(status_code=400, detail="Esta solicitação já foi analisada")

    novo_integrante = models.Integrante(
        nome=solicitacao.nome,
        apelido=solicitacao.apelido_desejado,
        data_nascimento=solicitacao.data_nascimento,
        cargo="Prospero",
        telefone=solicitacao.telefone,
        email=solicitacao.email,
        moto_modelo=solicitacao.moto_modelo,
        status="Ativo",
    )
    db.add(novo_integrante)
    db.flush()  # garante o id antes de criar o usuário de acesso

    login_gerado = _gerar_login(solicitacao.nome, db)
    senha_temporaria = secrets.token_urlsafe(6)
    novo_usuario = models.Usuario(
        integrante_id=novo_integrante.id,
        login=login_gerado,
        senha_hash=auth.gerar_hash_senha(senha_temporaria),
        cargo="Prospero",
    )
    db.add(novo_usuario)

    solicitacao.status = "Aprovada"
    solicitacao.analisado_por_id = usuario.integrante_id
    solicitacao.data_analise = datetime.utcnow()
    solicitacao.integrante_criado_id = novo_integrante.id

    db.commit()

    return schemas.SolicitacaoAprovarOut(
        integrante_id=novo_integrante.id,
        login_gerado=login_gerado,
        senha_temporaria=senha_temporaria,
    )


@app.post("/solicitacoes/{solicitacao_id}/recusar", response_model=schemas.SolicitacaoOut)
def recusar_solicitacao(
    solicitacao_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("analisar_solicitacoes")),
):
    solicitacao = db.query(models.SolicitacaoCadastro).filter(
        models.SolicitacaoCadastro.id == solicitacao_id
    ).first()
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    if solicitacao.status != "Pendente":
        raise HTTPException(status_code=400, detail="Esta solicitação já foi analisada")

    solicitacao.status = "Recusada"
    solicitacao.analisado_por_id = usuario.integrante_id
    solicitacao.data_analise = datetime.utcnow()
    db.commit()
    db.refresh(solicitacao)
    return solicitacao


# ---------- Meu perfil ----------
@app.get("/auth/me", response_model=schemas.MeuPerfil)
def meu_perfil(usuario: models.Usuario = Depends(auth.obter_usuario_atual)):
    return schemas.MeuPerfil(
        id=usuario.id,
        login=usuario.login,
        nome=usuario.integrante.nome if usuario.integrante else usuario.login,
        cargo=usuario.cargo,
        permissoes=sorted(auth.permissoes_do_usuario(usuario)),
    )


# ---------- Usuários, acessos e permissões ----------
def _usuario_para_out(u: models.Usuario) -> schemas.UsuarioOut:
    # Montado campo a campo: no banco 'permissoes_customizadas' é texto JSON,
    # enquanto no schema é dicionário — a conversão automática não serve aqui.
    return schemas.UsuarioOut(
        id=u.id,
        login=u.login,
        cargo=u.cargo,
        ativo=bool(u.ativo),
        integrante_id=u.integrante_id,
        integrante_nome=u.integrante.nome if u.integrante else None,
        permissoes_efetivas=sorted(auth.permissoes_do_usuario(u)),
        permissoes_customizadas=permissoes.carregar_customizadas(u.permissoes_customizadas),
    )


def _restariam_administradores(db: Session, usuario_alvo: models.Usuario) -> bool:
    """Confere se, além do usuário alvo, sobra alguém ativo com 'gerenciar_acessos'.

    Impede que o clube fique sem ninguém capaz de administrar o sistema.
    """
    outros = db.query(models.Usuario).filter(
        models.Usuario.id != usuario_alvo.id,
        models.Usuario.ativo.is_(True),
    ).all()
    return any("gerenciar_acessos" in auth.permissoes_do_usuario(u) for u in outros)


@app.get("/permissoes/catalogo", response_model=schemas.CatalogoPermissoes)
def catalogo_permissoes(
    usuario: models.Usuario = Depends(auth.exigir_permissao("gerenciar_acessos")),
):
    return schemas.CatalogoPermissoes(
        permissoes=permissoes.CATALOGO,
        cargos=permissoes.CARGOS,
        padroes_por_cargo=permissoes.PADROES_POR_CARGO,
    )


@app.get("/usuarios", response_model=list[schemas.UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("gerenciar_acessos")),
):
    return [_usuario_para_out(u) for u in db.query(models.Usuario).all()]


@app.patch("/usuarios/{usuario_id}", response_model=schemas.UsuarioOut)
def atualizar_usuario(
    usuario_id: int,
    dados: schemas.UsuarioAtualizar,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("gerenciar_acessos")),
):
    """Altera cargo e/ou status do acesso. O cargo é espelhado no integrante."""
    alvo = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if dados.cargo is not None:
        if dados.cargo not in permissoes.CARGOS:
            raise HTTPException(status_code=400, detail="Cargo inválido")
        alvo.cargo = dados.cargo
        if alvo.integrante:
            alvo.integrante.cargo = dados.cargo  # mantém os dois lados em sincronia

    if dados.ativo is not None:
        alvo.ativo = dados.ativo

    # trava: não deixar o sistema sem nenhum administrador ativo
    ainda_administra = alvo.ativo and "gerenciar_acessos" in auth.permissoes_do_usuario(alvo)
    if not ainda_administra and not _restariam_administradores(db, alvo):
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Esta alteração deixaria o sistema sem nenhum administrador ativo",
        )

    db.commit()
    db.refresh(alvo)
    return _usuario_para_out(alvo)


@app.put("/usuarios/{usuario_id}/permissoes", response_model=schemas.UsuarioOut)
def atualizar_permissoes(
    usuario_id: int,
    dados: schemas.PermissoesAtualizar,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("gerenciar_acessos")),
):
    """Define os ajustes individuais de permissão (por cima do padrão do cargo)."""
    alvo = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    desconhecidas = [c for c in dados.permissoes if c not in permissoes.TODAS]
    if desconhecidas:
        raise HTTPException(
            status_code=400, detail=f"Permissões inválidas: {', '.join(desconhecidas)}"
        )

    alvo.permissoes_customizadas = permissoes.serializar_customizadas(dados.permissoes)

    ainda_administra = alvo.ativo and "gerenciar_acessos" in auth.permissoes_do_usuario(alvo)
    if not ainda_administra and not _restariam_administradores(db, alvo):
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Esta alteração deixaria o sistema sem nenhum administrador ativo",
        )

    db.commit()
    db.refresh(alvo)
    return _usuario_para_out(alvo)


@app.post("/usuarios/{usuario_id}/resetar-senha", response_model=schemas.SenhaResetada)
def resetar_senha(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("gerenciar_acessos")),
):
    alvo = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    senha_temporaria = secrets.token_urlsafe(6)
    alvo.senha_hash = auth.gerar_hash_senha(senha_temporaria)
    db.commit()
    return schemas.SenhaResetada(login=alvo.login, senha_temporaria=senha_temporaria)


@app.post("/integrantes/{integrante_id}/criar-acesso", response_model=schemas.AcessoCriado)
def criar_acesso(
    integrante_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.exigir_permissao("gerenciar_acessos")),
):
    """Cria login para um integrante que ainda não tem acesso ao portal."""
    integrante = db.query(models.Integrante).filter(
        models.Integrante.id == integrante_id
    ).first()
    if not integrante:
        raise HTTPException(status_code=404, detail="Integrante não encontrado")
    if integrante.usuario:
        raise HTTPException(status_code=400, detail="Este integrante já possui acesso")

    login_gerado = _gerar_login(integrante.nome, db)
    senha_temporaria = secrets.token_urlsafe(6)
    novo = models.Usuario(
        integrante_id=integrante.id,
        login=login_gerado,
        senha_hash=auth.gerar_hash_senha(senha_temporaria),
        cargo=integrante.cargo or "Integrante",
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return schemas.AcessoCriado(
        usuario_id=novo.id, login=login_gerado, senha_temporaria=senha_temporaria
    )
