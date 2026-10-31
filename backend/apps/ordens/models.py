from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Final

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone


class TipoTecido(models.TextChoices):
    ALGODAO = "ALGODAO", "Algodão (Multiplicador 1.00x)"
    JEANS = "JEANS", "Jeans (Multiplicador 1.00x)"
    POLIESTER = "POLIESTER", "Poliéster (Multiplicador 1.00x)"
    OUTROS = "OUTROS", "Outros Tecidos Simples (Multiplicador 1.00x)"
    COURO = "COURO", "Couro Natural/Sintético (Multiplicador 1.40x)"
    SEDA = "SEDA", "Seda Pura (Multiplicador 1.40x)"
    VELUDO = "VELUDO", "Veludo (Multiplicador 1.40x)"
    PEDRARIAS = "PEDRARIAS", "Renda / Pedrarias / Bordados (Multiplicador 1.40x)"

    @classmethod
    def tecidos_complexos(cls) -> set[str]:
        return {
            cls.COURO.value,
            cls.SEDA.value,
            cls.VELUDO.value,
            cls.PEDRARIAS.value,
        }

    @classmethod
    def obter_multiplicador(cls, tipo_tecido: str) -> Decimal:
        if tipo_tecido in cls.tecidos_complexos():
            return Decimal("1.40")
        return Decimal("1.00")


class StatusOS(models.TextChoices):
    CRIADA = "CRIADA", "Criada (Aguardando Triagem)"
    ORCADA = "ORCADA", "Orçada (Validade de 7 dias)"
    APROVADA = "APROVADA", "Aprovada (Aguardando Início/Sinal)"
    EM_COSTURA = "EM_COSTURA", "Em Costura (Na Bancada)"
    PRONTA_PARA_PROVA = "PRONTA_PARA_PROVA", "Pronta para Prova Presencial"
    PRONTA_PARA_RETIRADA = "PRONTA_PARA_RETIRADA", "Pronta para Retirada"
    FINALIZADA = "FINALIZADA", "Finalizada (Entregue e Quitada)"
    CANCELADA = "CANCELADA", "Cancelada"


ALLOWED_IMAGE_MIME_TYPES: Final[set[str]] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_UPLOAD_SIZE_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB


def validar_arquivo_imagem(arquivo: models.fields.files.FieldFile) -> None:
    if not arquivo:
        return
    file_obj = getattr(arquivo, "file", None)
    content_type = getattr(file_obj, "content_type", None)
    if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValidationError(
            f"Tipo MIME '{content_type}' inválido. Permitidos: {', '.join(sorted(ALLOWED_IMAGE_MIME_TYPES))}."
        )
    if arquivo.size and arquivo.size > MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError("O arquivo de imagem excede o tamanho máximo permitido de 5MB.")


class OrdemServico(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID da Ordem de Serviço",
    )
    codigo_protocolo = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="Código de Protocolo",
    )
    cliente_nome = models.CharField(
        max_length=150,
        verbose_name="Nome Completo do Cliente",
    )
    cliente_telefone = models.CharField(
        max_length=25,
        verbose_name="Telefone / WhatsApp",
    )
    cliente_email = models.EmailField(
        blank=True,
        default="",
        verbose_name="E-mail do Cliente",
    )
    descricao_peca = models.CharField(
        max_length=255,
        verbose_name="Descrição da Peça",
    )
    tipo_tecido = models.CharField(
        max_length=20,
        choices=TipoTecido.choices,
        default=TipoTecido.ALGODAO,
        verbose_name="Tipo de Tecido",
    )
    status = models.CharField(
        max_length=25,
        choices=StatusOS.choices,
        default=StatusOS.CRIADA,
        db_index=True,
        verbose_name="Status da OS",
    )
    taxa_higienizacao_ativa = models.BooleanField(
        default=False,
        verbose_name="Incluir Taxa de Higienização (R$ 35,00)",
    )
    prazo_entrega_horas = models.PositiveIntegerField(
        default=72,
        validators=[MinValueValidator(1)],
        verbose_name="Prazo de Entrega Estimado (em horas)",
    )
    termo_avarias_aceito = models.BooleanField(
        default=False,
        verbose_name="Termo de Vistoria e Avarias Aceito",
    )
    checklist_avarias = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Checklist Estruturado de Avarias",
    )
    observacoes_triagem = models.TextField(
        blank=True,
        default="",
        verbose_name="Observações Técnicas de Triagem",
    )
    subtotal_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Subtotal Base dos Serviços",
    )
    multiplicador_aplicado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("1.00"))],
        verbose_name="Multiplicador de Tecido Aplicado",
    )
    subtotal_tecido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Subtotal com Complexidade de Tecido",
    )
    taxa_higienizacao_valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Valor da Taxa de Higienização",
    )
    taxa_urgencia_valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Valor da Taxa de Urgência (< 48h)",
    )
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Valor Total do Orçamento",
    )
    valor_pago = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Valor Total Pago pelo Cliente",
    )
    validade_orcamento_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Validade do Orçamento (7 dias)",
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação",
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Atualização",
    )

    class Meta:
        db_table = "ordens_servico"
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"
        ordering = ["-criado_em"]
        constraints = [
            CheckConstraint(
                check=Q(valor_total__gte=Decimal("0.00")),
                name="ck_os_valor_total_nao_negativo",
            ),
            CheckConstraint(
                check=Q(valor_pago__gte=Decimal("0.00")),
                name="ck_os_valor_pago_nao_negativo",
            ),
            CheckConstraint(
                check=Q(prazo_entrega_horas__gte=1),
                name="ck_os_prazo_entrega_positivo",
            ),
        ]

    def __str__(self) -> str:
        return f"OS {self.codigo_protocolo} - {self.cliente_nome} ({self.status})"

    @property
    def urgente(self) -> bool:
        return self.prazo_entrega_horas < 48

    @property
    def saldo_devedor(self) -> Decimal:
        saldo = self.valor_total - self.valor_pago
        return saldo if saldo > Decimal("0.00") else Decimal("0.00")

    def definir_validade_orcamento(self) -> None:
        self.validade_orcamento_em = timezone.now() + timedelta(days=7)

    def clean(self) -> None:
        super().clean()
        if self.valor_pago < Decimal("0.00"):
            raise ValidationError({"valor_pago": "O valor pago não pode ser negativo."})
        if self.valor_total < Decimal("0.00"):
            raise ValidationError({"valor_total": "O valor total não pode ser negativo."})


class ItemOrdemServico(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name="Ordem de Serviço",
    )
    nome_servico = models.CharField(
        max_length=140,
        verbose_name="Descrição do Serviço/Ajuste",
    )
    detalhes_execucao = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Especificações de Costura",
    )
    valor_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Valor Base Unitário (R$)",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ordens_servico_itens"
        verbose_name = "Item da Ordem de Serviço"
        verbose_name_plural = "Itens da Ordem de Serviço"
        constraints = [
            CheckConstraint(
                check=Q(valor_base__gt=Decimal("0.00")),
                name="ck_item_os_valor_base_positivo",
            )
        ]

    def __str__(self) -> str:
        return f"{self.nome_servico} (R$ {self.valor_base})"


class FotoInspecaoOS(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name="fotos",
        verbose_name="Ordem de Serviço",
    )
    imagem = models.ImageField(
        upload_to="inspecoes_os/%Y/%m/%d/",
        validators=[validar_arquivo_imagem],
        verbose_name="Arquivo de Imagem Comprimido",
    )
    mime_type = models.CharField(
        max_length=50,
        default="image/jpeg",
        verbose_name="MIME Type Verificado",
    )
    tamanho_bytes = models.PositiveIntegerField(
        default=0,
        verbose_name="Tamanho do Arquivo (Bytes)",
    )
    legenda_avaria = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Identificação da Avaria / Ângulo",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ordens_servico_fotos"
        verbose_name = "Foto de Inspeção da OS"
        verbose_name_plural = "Fotos de Inspeção da OS"

    def clean(self) -> None:
        super().clean()
        if self.mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValidationError(
                {"mime_type": f"MIME type '{self.mime_type}' não permitido."}
            )


class HistoricoStatusOS(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.CASCADE,
        related_name="historico_status",
    )
    status_anterior = models.CharField(
        max_length=25,
        choices=StatusOS.choices,
    )
    status_novo = models.CharField(
        max_length=25,
        choices=StatusOS.choices,
    )
    motivo = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ordens_servico_historico_status"
        ordering = ["-registrado_em"]
