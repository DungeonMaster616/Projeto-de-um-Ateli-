from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
    FotoInspecaoOS,
    HistoricoStatusOS,
    ItemOrdemServico,
    OrdemServico,
    StatusOS,
    TipoTecido,
)
from .services import OrdemServicoService


class ItemOrdemServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemOrdemServico
        fields = [
            "id",
            "nome_servico",
            "detalhes_execucao",
            "valor_base",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em"]

    def validate_nome_servico(self, value: str) -> str:
        limpo = value.strip()
        if len(limpo) < 3:
            raise serializers.ValidationError(
                "O nome do serviço deve conter ao menos 3 caracteres."
            )
        return limpo

    def validate_valor_base(self, value: Decimal) -> Decimal:
        if value <= Decimal("0.00"):
            raise serializers.ValidationError(
                "O valor base do item deve ser maior que R$ 0,00."
            )
        return value


class FotoInspecaoOSSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoInspecaoOS
        fields = [
            "id",
            "imagem",
            "mime_type",
            "tamanho_bytes",
            "legenda_avaria",
            "criado_em",
        ]
        read_only_fields = ["id", "mime_type", "tamanho_bytes", "criado_em"]

    def validate_imagem(self, arquivo: Any) -> Any:
        content_type = getattr(arquivo, "content_type", "")
        if content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise serializers.ValidationError(
                f"Formato de imagem não suportado ({content_type}). "
                f"Envie JPEG, PNG ou WEBP."
            )
        if arquivo.size > MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError(
                "A imagem excede o limite máximo de 5MB após compressão."
            )
        return arquivo


class HistoricoStatusOSSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricoStatusOS
        fields = [
            "id",
            "status_anterior",
            "status_novo",
            "motivo",
            "registrado_em",
        ]
        read_only_fields = fields


class OrdemServicoCreateSerializer(serializers.ModelSerializer):
    itens = ItemOrdemServicoSerializer(many=True, write_only=True)
    fotos_upload = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    emitir_orcamento_imediato = serializers.BooleanField(
        write_only=True,
        default=True,
    )

    class Meta:
        model = OrdemServico
        fields = [
            "id",
            "codigo_protocolo",
            "cliente_nome",
            "cliente_telefone",
            "cliente_email",
            "descricao_peca",
            "tipo_tecido",
            "status",
            "taxa_higienizacao_ativa",
            "prazo_entrega_horas",
            "termo_avarias_aceito",
            "checklist_avarias",
            "observacoes_triagem",
            "subtotal_base",
            "multiplicador_aplicado",
            "subtotal_tecido",
            "taxa_higienizacao_valor",
            "taxa_urgencia_valor",
            "valor_total",
            "valor_pago",
            "validade_orcamento_em",
            "itens",
            "fotos_upload",
            "emitir_orcamento_imediato",
            "criado_em",
        ]
        read_only_fields = [
            "id",
            "codigo_protocolo",
            "status",
            "subtotal_base",
            "multiplicador_aplicado",
            "subtotal_tecido",
            "taxa_higienizacao_valor",
            "taxa_urgencia_valor",
            "valor_total",
            "validade_orcamento_em",
            "criado_em",
        ]

    def validate_itens(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise serializers.ValidationError(
                "É obrigatório informar ao menos 1 item de serviço na OS."
            )
        return value

    def validate_fotos_upload(self, arquivos: list[Any]) -> list[Any]:
        for arquivo in arquivos:
            content_type = getattr(arquivo, "content_type", "")
            if content_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise serializers.ValidationError(
                    f"Arquivo '{arquivo.name}' possui MIME '{content_type}' inválido."
                )
            if arquivo.size > MAX_UPLOAD_SIZE_BYTES:
                raise serializers.ValidationError(
                    f"Arquivo '{arquivo.name}' excede o tamanho máximo de 5MB."
                )
        return arquivos

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        emitir_orcamento = attrs.get("emitir_orcamento_imediato", True)
        termo_aceito = attrs.get("termo_avarias_aceito", False)
        fotos = attrs.get("fotos_upload", [])

        if emitir_orcamento:
            if not termo_aceito:
                raise serializers.ValidationError(
                    {
                        "termo_avarias_aceito": (
                            "RN-TRI-001: O aceite do termo de vistoria de avarias é obrigatório "
                            "para emissão do orçamento."
                        )
                    }
                )
            if len(fotos) < 1:
                raise serializers.ValidationError(
                    {
                        "fotos_upload": (
                            "RN-TRI-001: É obrigatório anexar ao menos 1 foto da peça "
                            "para transicionar a OS para ORCADA."
                        )
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> OrdemServico:
        itens_data = validated_data.pop("itens")
        fotos_upload = validated_data.pop("fotos_upload", [])
        emitir_orcamento = validated_data.pop("emitir_orcamento_imediato", True)

        protocolo = f"BEL-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        ordem = OrdemServico.objects.create(
            codigo_protocolo=protocolo,
            status=StatusOS.CRIADA,
            **validated_data,
        )

        for item in itens_data:
            ItemOrdemServico.objects.create(ordem_servico=ordem, **item)

        for foto in fotos_upload:
            FotoInspecaoOS.objects.create(
                ordem_servico=ordem,
                imagem=foto,
                mime_type=getattr(foto, "content_type", "image/jpeg"),
                tamanho_bytes=getattr(foto, "size", 0),
                legenda_avaria="Registro fotográfico de entrada (triagem)",
            )

        ordem = OrdemServicoService.sincronizar_orcamento_os(str(ordem.id))

        if emitir_orcamento:
            ordem = OrdemServicoService.transicionar_status(
                os_id=str(ordem.id),
                novo_status=StatusOS.ORCADA,
                motivo="Triagem fotográfica e cálculo automático concluídos na abertura.",
            )

        return ordem


class OrdemServicoDetailSerializer(serializers.ModelSerializer):
    itens = ItemOrdemServicoSerializer(many=True, read_only=True)
    fotos = FotoInspecaoOSSerializer(many=True, read_only=True)
    historico_status = HistoricoStatusOSSerializer(many=True, read_only=True)
    saldo_devedor = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    urgente = serializers.BooleanField(read_only=True)
    tipo_tecido_display = serializers.CharField(
        source="get_tipo_tecido_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = OrdemServico
        fields = [
            "id",
            "codigo_protocolo",
            "cliente_nome",
            "cliente_telefone",
            "cliente_email",
            "descricao_peca",
            "tipo_tecido",
            "tipo_tecido_display",
            "status",
            "status_display",
            "taxa_higienizacao_ativa",
            "prazo_entrega_horas",
            "urgente",
            "termo_avarias_aceito",
            "checklist_avarias",
            "observacoes_triagem",
            "subtotal_base",
            "multiplicador_aplicado",
            "subtotal_tecido",
            "taxa_higienizacao_valor",
            "taxa_urgencia_valor",
            "valor_total",
            "valor_pago",
            "saldo_devedor",
            "validade_orcamento_em",
            "itens",
            "fotos",
            "historico_status",
            "criado_em",
            "atualizado_em",
        ]


class TransicaoStatusSerializer(serializers.Serializer):
    novo_status = serializers.ChoiceField(choices=StatusOS.choices)
    motivo = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )


class RegistroPagamentoSerializer(serializers.Serializer):
    valor_recebido = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
