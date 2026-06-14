from pydantic import BaseModel
from typing import Optional


class Estatisticas(BaseModel):
    atk: int
    def_: int
    spd: int
    int_: int

    class Config:
        populate_by_name = True


class Heroi(BaseModel):
    id: str
    nome: str
    classe: str
    nivel: int
    avatar: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    xp: int
    xp_next: int
    gold: int
    active_quests: list[str]
    completed_quests: list[str]

    class Config:
        populate_by_name = True


class RespostaHeroi(BaseModel):
    id: str
    nome: str
    nome_classe: str
    nivel: int
    avatar: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    xp: int
    xp_next: int
    gold: int
    estatisticas: dict
    active_quests: list[str]
    completed_quests: list[str]
    links: dict


class RespostaEstatisticas(BaseModel):
    id_heroi: str
    atk: int
    def_: int
    spd: int
    int_: int
    links: dict


class SolicitacaoAdicionarXp(BaseModel):
    quantidade: int


class RespostaAdicionarXp(BaseModel):
    id_heroi: str
    xp_ganho: int
    xp_total: int
    subiu_de_nivel: bool
    novo_nivel: Optional[int]
    links: dict


class SolicitacaoAlterarGold(BaseModel):
    quantidade: int


class RespostaAlterarGold(BaseModel):
    id_heroi: str
    gold: int
    links: dict


class RespostaCheckout(BaseModel):
    id: str
    nome: str
    nome_classe: str
    nivel: int
    avatar: str
    status: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    xp: int
    xp_next: int
    gold: int
    estatisticas: dict
    links: dict


class RespostaCheckin(BaseModel):
    id: str
    status: str
    message: str
    links: dict
