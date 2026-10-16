from typing import Tuple

def aplicar_triagem_limiar_duplo(
    score_similaridade: float,
    limiar_aprovado: float = 0.95,
    limiar_reprovado: float = 0.85
) -> Tuple[str, str]:
    """Aplica a regra de decisão industrial para classificação da peça."""
    if score_similaridade >= limiar_aprovado:
        return "APROVADO", "Sinal Verde — Peça em conformidade"
    elif score_similaridade <= limiar_reprovado:
        return "REPROVADO", "Sinal Vermelho — Acionar ejetor P7"
    else:
        return "DUVIDA", "Sinal Amarelo — Encaminhar para Revisão Humana (HITL)"