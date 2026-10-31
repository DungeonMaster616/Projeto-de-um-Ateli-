from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from .models import FotoInspecaoOS, OrdemServico
from .serializers import (
    FotoInspecaoOSSerializer,
    OrdemServicoCreateSerializer,
    OrdemServicoDetailSerializer,
    RegistroPagamentoSerializer,
    TransicaoStatusSerializer,
)
from .services import (
    OrdemServicoService,
    RegraDeNegocioException,
    TransicaoDeEstadoInvalidaException,
)


class OrdemServicoViewSet(viewsets.ModelViewSet):
    queryset = OrdemServico.objects.prefetch_related(
        "itens",
        "fotos",
        "historico_status",
    ).all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self) -> type:
        if self.action == "create":
            return OrdemServicoCreateSerializer
        return OrdemServicoDetailSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ordem = serializer.save()
        except RegraDeNegocioException as exc:
            return Response(
                {
                    "erro": exc.codigo,
                    "mensagem": exc.mensagem,
                },
                status=exc.status_http,
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "erro": "VALIDACAO_DOMINIO",
                    "mensagem": exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        output_serializer = OrdemServicoDetailSerializer(
            ordem,
            context={"request": request},
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="transicionar-status")
    def transicionar_status(self, request: Request, pk: str | None = None) -> Response:
        ordem = get_object_or_404(OrdemServico, pk=pk)
        serializer = TransicaoStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ordem_atualizada = OrdemServicoService.transicionar_status(
                os_id=str(ordem.id),
                novo_status=serializer.validated_data["novo_status"],
                motivo=serializer.validated_data.get("motivo", ""),
            )
        except TransicaoDeEstadoInvalidaException as exc:
            return Response(
                {
                    "erro": exc.codigo,
                    "mensagem": exc.mensagem,
                    "status_atual": ordem.status,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except RegraDeNegocioException as exc:
            return Response(
                {
                    "erro": exc.codigo,
                    "mensagem": exc.mensagem,
                    "status_atual": ordem.status,
                },
                status=exc.status_http,
            )

        return Response(
            OrdemServicoDetailSerializer(
                ordem_atualizada,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="registrar-pagamento")
    def registrar_pagamento(self, request: Request, pk: str | None = None) -> Response:
        ordem = get_object_or_404(OrdemServico, pk=pk)
        serializer = RegistroPagamentoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ordem_atualizada = OrdemServicoService.registrar_pagamento(
                os_id=str(ordem.id),
                valor_recebido=serializer.validated_data["valor_recebido"],
            )
        except RegraDeNegocioException as exc:
            return Response(
                {
                    "erro": exc.codigo,
                    "mensagem": exc.mensagem,
                },
                status=exc.status_http,
            )

        return Response(
            OrdemServicoDetailSerializer(
                ordem_atualizada,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="adicionar-foto")
    def adicionar_foto(self, request: Request, pk: str | None = None) -> Response:
        ordem = get_object_or_404(OrdemServico, pk=pk)
        serializer = FotoInspecaoOSSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        arquivo = serializer.validated_data["imagem"]
        foto = FotoInspecaoOS.objects.create(
            ordem_servico=ordem,
            imagem=arquivo,
            mime_type=getattr(arquivo, "content_type", "image/jpeg"),
            tamanho_bytes=getattr(arquivo, "size", 0),
            legenda_avaria=serializer.validated_data.get("legenda_avaria", ""),
        )
        return Response(
            FotoInspecaoOSSerializer(foto, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
