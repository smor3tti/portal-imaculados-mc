"""
Portal Imaculados M.C. - Cria o primeiro usuário (Presidente) para testes.

Uso:
    python criar_admin.py
"""
from datetime import date

from auth import gerar_hash_senha
from database import SessionLocal, init_db
import models


def main():
    init_db()
    db = SessionLocal()
    try:
        if db.query(models.Usuario).filter(models.Usuario.login == "presidente").first():
            print("Usuário 'presidente' já existe.")
            return

        integrante = models.Integrante(
            nome="Presidente Imaculados",
            apelido="Presidente",
            cargo="Presidente",
            data_entrada=date.today(),
            status="Ativo",
        )
        db.add(integrante)
        db.flush()  # garante integrante.id antes de criar o usuário

        usuario = models.Usuario(
            integrante_id=integrante.id,
            login="presidente",
            senha_hash=gerar_hash_senha("imaculados123"),
            cargo="Presidente",
        )
        db.add(usuario)
        db.commit()
        print("Usuário criado -> login: presidente | senha: imaculados123")
        print("IMPORTANTE: troque essa senha assim que possível.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
