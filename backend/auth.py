"""
Portal Imaculados M.C. - Autenticação (hash de senha + JWT)
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
import models
import permissoes

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verificar_senha(senha_texto: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_texto, senha_hash)


def gerar_hash_senha(senha_texto: str) -> str:
    return pwd_context.hash(senha_texto)


def criar_access_token(dados: dict, expira_em: Optional[timedelta] = None) -> str:
    dados_copia = dados.copy()
    expira = datetime.utcnow() + (expira_em or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    dados_copia.update({"exp": expira})
    return jwt.encode(dados_copia, SECRET_KEY, algorithm=ALGORITHM)


def autenticar_usuario(db: Session, login: str, senha: str) -> Optional[models.Usuario]:
    usuario = db.query(models.Usuario).filter(models.Usuario.login == login).first()
    if not usuario or not usuario.ativo:
        return None
    if not verificar_senha(senha, usuario.senha_hash):
        return None
    return usuario


def obter_usuario_atual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id: str = payload.get("sub")
        if usuario_id is None:
            raise credenciais_invalidas
    except JWTError:
        raise credenciais_invalidas

    usuario = db.query(models.Usuario).filter(models.Usuario.id == int(usuario_id)).first()
    if usuario is None:
        raise credenciais_invalidas
    return usuario


def exigir_cargo(*cargos_permitidos: str):
    """Dependency factory: restringe uma rota a determinados cargos."""
    def verificador(usuario: models.Usuario = Depends(obter_usuario_atual)):
        if usuario.cargo not in cargos_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso",
            )
        return usuario
    return verificador


def permissoes_do_usuario(usuario: models.Usuario) -> set:
    """Permissões finais do usuário (padrão do cargo + ajustes individuais)."""
    return permissoes.efetivas(usuario.cargo, usuario.permissoes_customizadas)


def exigir_permissao(*chaves_necessarias: str):
    """Dependency factory: exige uma ou mais permissões específicas.

    Preferir esta função a exigir_cargo, pois respeita os ajustes individuais
    feitos pela diretoria em cada usuário.
    """
    def verificador(usuario: models.Usuario = Depends(obter_usuario_atual)):
        se_tem = permissoes_do_usuario(usuario)
        faltando = [c for c in chaves_necessarias if c not in se_tem]
        if faltando:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso",
            )
        return usuario
    return verificador
