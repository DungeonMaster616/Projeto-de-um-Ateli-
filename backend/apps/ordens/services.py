from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Final, Iterable

from django.db import transaction

from .models import (
    HistoricoStatusOS,
    ItemOrdemServico,
    OrdemServico,
    StatusOS,
    TipoTecido,
)

TWO_PLACES: Final[Decimal] = Decimal("0.01")
TAXA_HIGIENIZACAO_FIXA: Final[Decimal] = Decimal("35.00")
PERCENTUAL_TAXA_URGENCIA: Final[Decimal] = Decimal("0.30")
LIMITE_DISPENSA_SINAL: Final[Decimal] = Decimal("80.00")
PERCENTUAL_SINAL_MINIMO: Final[Decimal] = Decimal("0.50")


class RegraDeNegocioException(Exception):
    def __init__(self, codigo: str, mensagem: str, status_http: int = 422) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status_http = status_http


class TransicaoDeEstadoInvalidaException(RegraDeNegocioException):
    def __init__(self, status_atual: str, status_destino: str, detalhe: str = "") -> None:
        msg = f"Transição inválida de '{status_atual}' para '{status_destino}'."
        if detalhe:
            msg = f"{msg} {detalhe}"
        super().__init__(
            codigo="RN-FSM-INVALID",
            mensagem=msg,
            status_http=409,
        )


@dataclass(frozen=True)
class ResultadoCalculoOrcamento:
    subtotal_base: Decimal
    multiplicador_aplicado: Decimal
    subtotal_tecido: Decimal
    taxa_higienizacao_valor: Decimal
    taxa_urgencia_valor: Decimal
    taxas_adicionais: Decimal
    valor_total: Decimal
    sinal_minimo_exigido: Decimal


def arredondar_moeda(valor: Decimal) -> Decimal:
    return valor.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class OrdemServicoService:
    TRANSICOES_PERMITIDAS: Final[dict[str, set[str]]] = {
        StatusOS.CRIADA: {StatusOS.ORCADA, StatusOS.CANCELADA},
        StatusOS.ORCADA: {StatusOS.APROVADA, StatusOS.CANCELADA},
        StatusOS.APROVADA: {StatusOS.EM_COSTURA, StatusOS.CANCELADA},
        StatusOS.EM_COSTURA: {StatusOS.PRONTA_PARA_PROVA, StatusOS.PRONTA_PARA_RETIRADA},
        StatusOS.PRONTA_PARA_PROVA: {StatusOS.EM_COSTURA, StatusOS.PRONTA_PARA_RETIRADA},
        StatusOS.PRONTA_PARA_RETIRADA: {StatusOS.FINALIZADA},
        StatusOS.FINALIZADA: set(),
        StatusOS.CANCELADA: set(),
    }

    @classmethod
    def calcular_orcamento_deterministico(
        cls,
        valores_base_itens: Iterable[Decimal],
        tipo_tecido: str,
        taxa_higienizacao_ativa: bool,
        prazo_entrega_horas: int,
    ) -> ResultadoCalculoOrcamento:
        lista_valores = [arredondar_moeda(Decimal(str(v))) for v in valores_base_itens]
        if not lista_valores:
            raise RegraDeNegocioException(
                codigo="RN-ORC-001",
                mensagem="A Ordem de Serviço deve possuir ao menos 1 item de serviço para cálculo do orçamento.",
                status_http=400,
            )

        subtotal_base = arredondar_moeda(sum(lista_valores, Decimal("0.00")))
        multiplicador = TipoTecido.obter_multiplicador(tipo_tecido)
        subtotal_tecido = arredondar_moeda(subtotal_base * multiplicador)

        taxa_higienizacao = (
            TAXA_HIGIENIZACAO_FIXA if taxa_higienizacao_ativa else Decimal("0.00")
        )
        taxa_urgencia = (
            arredondar_moeda(subtotal_tecido * PERCENTUAL_TAXA_URGENCIA)
            if prazo_entrega_horas < 48
            else Decimal("0.00")
        )

        taxas_adicionais = arredondar_moeda(taxa_higienizacao + taxa_urgencia)
        valor_total = arredondar_moeda(subtotal_tecido + taxas_adicionais)

        sinal_minimo = (
            arredondar_moeda(valor_total * PERCENTUAL_SINAL_MINIMO)
            if valor_total > LIMITE_DISPENSA_SINAL
            else Decimal("0.00")
        )

        return ResultadoCalculoOrcamento(
            subtotal_base=subtotal_base,
            multiplicador_aplicado=multiplicador,
            subtotal_tecido=subtotal_tecido,
            taxa_higienizacao_valor=taxa_higienizacao,
            taxa_urgencia_valor=taxa_urgencia,
            taxas_adicionais=taxas_adicionais,
            valor_total=valor_total,
            sinal_minimo_exigido=sinal_minimo,
        )

    @classmethod
    @transaction.atomic
    def sincronizar_orcamento_os(cls, os_id: str) -> OrdemServico:
        ordem = OrdemServico.objects.select_for_update().get(pk=os_id)
        itens = list(ItemOrdemServico.objects.filter(ordem_servico=ordem))
        valores = [item.valor_base for item in itens]

        resultado = cls.calcular_orcamento_deterministico(
            valores_base_itens=valores,
            tipo_tecido=ordem.tipo_tecido,
            taxa_higienizacao_ativa=ordem.taxa_higienizacao_ativa,
            prazo_entrega_horas=ordem.prazo_entrega_horas,
        )

        ordem.subtotal_base = resultado.subtotal_base
        ordem.multiplicador_aplicado = resultado.multiplicador_aplicado
        ordem.subtotal_tecido = resultado.subtotal_tecido
        ordem.taxa_higienizacao_valor = resultado.taxa_higienizacao_valor
        ordem.taxa_urgencia_valor = resultado.taxa_urgencia_valor
        ordem.valor_total = resultado.valor_total
        ordem.full_clean()
        ordem.save(
            update_fields=[
                "subtotal_base",
                "multiplicador_aplicado",
                "subtotal_tecido",
                "taxa_higienizacao_valor",
                "taxa_urgencia_valor",
                "valor_total",
                "atualizado_em",
            ]
        )
        return ordem

    @classmethod
    @transaction.atomic
    def registrar_pagamento(
        cls,
        os_id: str,
        valor_recebido: Decimal,
    ) -> OrdemServico:
        quantia = arredondar_moeda(Decimal(str(valor_recebido)))
        if quantia <= Decimal("0.00"):
            raise RegraDeNegocioException(
                codigo="RN-FIN-000",
                mensagem="O valor do pagamento deve ser estritamente maior que zero.",
                status_http=400,
            )

        ordem = OrdemServico.objects.select_for_update().get(pk=os_id)
        if ordem.status == StatusOS.CANCELADA:
            raise RegraDeNegocioException(
                codigo="RN-FIN-CANCELADA",
                mensagem="Não é permitido registrar pagamentos para uma Ordem de Serviço cancelada.",
                status_http=409,
            )

        novo_total_pago = arredondar_moeda(ordem.valor_pago + quantia)
        if novo_total_pago > ordem.valor_total:
            raise RegraDeNegocioException(
                codigo="RN-FIN-EXCESSO",
                mensagem=(
                    f"O pagamento informado (R$ {quantia}) excede o saldo devedor "
                    f"atual de R$ {ordem.saldo_devedor}."
                ),
                status_http=422,
            )

        ordem.valor_pago = novo_total_pago
        ordem.full_clean()
        ordem.save(update_fields=["valor_pago", "atualizado_em"])
        return ordem

    @classmethod
    @transaction.atomic
    def transicionar_status(
        cls,
        os_id: str,
        novo_status: str,
        motivo: str = "",
    ) -> OrdemServico:
        ordem = OrdemServico.objects.select_for_update().get(pk=os_id)
        status_atual = ordem.status

        destinos_validos = cls.TRANSICOES_PERMITIDAS.get(status_atual, set())
        if novo_status not in destinos_validos:
            raise TransicaoDeEstadoInvalidaException(
                status_atual=status_atual,
                status_destino=novo_status,
                detalhe="Fluxo não permitido pela máquina de estados do Ateliê da Belinha.",
            )

        # Recalcula orçamento antes de validar travas financeiras e de triagem
        if ordem.itens.exists():
            ordem = cls.sincronizar_orcamento_os(str(ordem.id))

        # Trava RN-TRI-001: CRIADA -> ORCADA exige ao menos 1 foto e termo_avarias_aceito = True
        if status_atual == StatusOS.CRIADA and novo_status == StatusOS.ORCADA:
            quantidade_fotos = ordem.fotos.count()
            if quantidade_fotos < 1 or not ordem.termo_avarias_aceito:
                raise RegraDeNegocioException(
                    codigo="RN-TRI-001",
                    mensagem=(
                        "Trava de Avaria (RN-TRI-001): Nenhuma OS transita de CRIADA para ORCADA "
                        "sem ao menos 1 registro fotográfico de inspeção e o aceite obrigatório "
                        "do termo de avarias (termo_avarias_aceito = True)."
                    ),
                    status_http=422,
                )
            ordem.definir_validade_orcamento()

        # Trava RN-FIN-001: APROVADA -> EM_COSTURA exige sinal de 50% se valor_total > 80.00
        if status_atual == StatusOS.APROVADA and novo_status == StatusOS.EM_COSTURA:
            sinal_minimo = arredondar_moeda(ordem.valor_total * PERCENTUAL_SINAL_MINIMO)
            if ordem.valor_total > LIMITE_DISPENSA_SINAL and ordem.valor_pago < sinal_minimo:
                raise RegraDeNegocioException(
                    codigo="RN-FIN-001",
                    mensagem=(
                        f"Trava de Início (RN-FIN-001): Para orçamentos acima de R$ 80,00, "
                        f"o início da costura exige pagamento mínimo de 50% (R$ {sinal_minimo}). "
                        f"Valor pago atual: R$ {ordem.valor_pago}."
                    ),
                    status_http=422,
                )

        # Trava RN-FIN-002: Transição para FINALIZADA exige quitação integral (valor_pago >= valor_total)
        if novo_status == StatusOS.FINALIZADA:
            if ordem.valor_pago < ordem.valor_total:
                raise RegraDeNegocioException(
                    codigo="RN-FIN-002",
                    mensagem=(
                        f"Trava de Despacho/Entrega (RN-FIN-002): A Ordem de Serviço não pode ser "
                        f"FINALIZADA com saldo pendente. Valor Total: R$ {ordem.valor_total} | "
                        f"Valor Pago: R$ {ordem.valor_pago} | Saldo Devedor: R$ {ordem.saldo_devedor}."
                    ),
                    status_http=422,
                )

        ordem.status = novo_status
        ordem.full_clean()
        ordem.save(update_fields=["status", "validade_orcamento_em", "atualizado_em"])

        HistoricoStatusOS.objects.create(
            ordem_servico=ordem,
            status_anterior=status_atual,
            status_novo=novo_status,
            motivo=motivo.strip(),
        )

        return ordem
