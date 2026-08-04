"""
Portal Imaculados M.C. - Catálogo de permissões e padrões por cargo.

Cada cargo tem um conjunto padrão de permissões. Além disso, cada usuário pode
ter ajustes individuais (liberar ou bloquear itens específicos), guardados em
Usuario.permissoes_customizadas como JSON: {"ver_financeiro": true, ...}.
"""
import json
from typing import Optional

# ---------- Catálogo ----------
# grupo -> usado para agrupar visualmente na tela de permissões
CATALOGO = [
    {"chave": "ver_dashboard", "label": "Ver o dashboard", "grupo": "Geral"},

    {"chave": "ver_integrantes", "label": "Ver a lista de integrantes", "grupo": "Integrantes"},
    {"chave": "editar_integrantes", "label": "Cadastrar e editar integrantes", "grupo": "Integrantes"},
    {"chave": "excluir_integrantes", "label": "Excluir integrantes", "grupo": "Integrantes"},

    {"chave": "ver_financeiro", "label": "Ver mensalidades e caixa", "grupo": "Financeiro"},
    {"chave": "editar_financeiro", "label": "Lançar mensalidades e registrar pagamentos", "grupo": "Financeiro"},

    {"chave": "ver_eventos", "label": "Ver eventos e confirmar presença", "grupo": "Eventos"},
    {"chave": "editar_eventos", "label": "Criar, editar e excluir eventos", "grupo": "Eventos"},

    {"chave": "ver_comunicados", "label": "Ver comunicados", "grupo": "Comunicados"},
    {"chave": "editar_comunicados", "label": "Publicar e excluir comunicados", "grupo": "Comunicados"},

    {"chave": "ver_documentos", "label": "Ver e baixar documentos", "grupo": "Documentos"},
    {"chave": "editar_documentos", "label": "Enviar e excluir documentos", "grupo": "Documentos"},

    {"chave": "ver_solicitacoes", "label": "Ver solicitações de ingresso", "grupo": "Solicitações"},
    {"chave": "analisar_solicitacoes", "label": "Aprovar e recusar solicitações", "grupo": "Solicitações"},

    {"chave": "gerenciar_acessos", "label": "Gerenciar acessos e permissões", "grupo": "Administração"},
]

TODAS = [p["chave"] for p in CATALOGO]

# ---------- Padrões por cargo ----------
_BASICO = ["ver_dashboard", "ver_eventos", "ver_comunicados"]
_INTEGRANTE = _BASICO + ["ver_integrantes", "ver_documentos"]
_DIRETORIA = _INTEGRANTE + [
    "editar_integrantes", "ver_financeiro",
    "editar_eventos", "editar_comunicados", "editar_documentos",
    "ver_solicitacoes", "analisar_solicitacoes",
]

PADROES_POR_CARGO = {
    "Presidente": list(TODAS),
    "Vice-Presidente": list(_DIRETORIA),
    "Diretor": list(_DIRETORIA),
    "Tesoureiro": _INTEGRANTE + ["ver_financeiro", "editar_financeiro", "editar_documentos"],
    "Disciplina": _INTEGRANTE + ["editar_comunicados"],
    "Integrante": list(_INTEGRANTE),
    "Prospero": list(_BASICO),
}

CARGOS = list(PADROES_POR_CARGO.keys())


def padrao_do_cargo(cargo: str) -> set[str]:
    return set(PADROES_POR_CARGO.get(cargo, _BASICO))


def carregar_customizadas(bruto: Optional[str]) -> dict:
    """Lê o JSON de ajustes individuais, tolerando valor nulo ou inválido."""
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except (ValueError, TypeError):
        return {}


def efetivas(cargo: str, customizadas_json: Optional[str]) -> set[str]:
    """Permissões finais = padrão do cargo + ajustes individuais por cima."""
    resultado = padrao_do_cargo(cargo)
    for chave, liberado in carregar_customizadas(customizadas_json).items():
        if chave not in TODAS:
            continue  # ignora chaves desconhecidas (ex.: catálogo mudou)
        if liberado:
            resultado.add(chave)
        else:
            resultado.discard(chave)
    return resultado


def serializar_customizadas(ajustes: dict) -> Optional[str]:
    """Guarda apenas os ajustes válidos; devolve None quando não há nenhum."""
    limpos = {c: bool(v) for c, v in (ajustes or {}).items() if c in TODAS}
    return json.dumps(limpos) if limpos else None
