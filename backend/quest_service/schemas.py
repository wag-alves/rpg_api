from typing import Optional

from pydantic import BaseModel


class Missao(BaseModel):
    id: str
    titulo: str
    descricao: str
    dificuldade: str
    cor_dificuldade: str
    recompensa_xp: int
    recompensa_ouro: int
    status: str
    id_heroi: Optional[str]
    aceito_em: Optional[str]
    concluido_em: Optional[str]
    icone: str
    links: dict


class RespostaListaMissoes(BaseModel):
    missoes: list[Missao]
    links: dict


class SolicitacaoAceitarMissao(BaseModel):
    id_heroi: str


class RespostaAceitarMissao(BaseModel):
    id_missao: str
    id_heroi: str
    status: str
    mensagem: str
    links: dict


class RespostaConcluirMissao(BaseModel):
    id_missao: str
    id_heroi: str
    status: str
    recompensa_xp: int
    recompensa_ouro: int
    mensagem: str
    links: dict
