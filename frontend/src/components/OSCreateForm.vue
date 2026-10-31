<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import imageCompression from "browser-image-compression";

export type TipoTecidoChoice =
  | "ALGODAO"
  | "JEANS"
  | "POLIESTER"
  | "OUTROS"
  | "COURO"
  | "SEDA"
  | "VELUDO"
  | "PEDRARIAS";

export interface ItemOrdemServicoInput {
  id_temp: string;
  nome_servico: string;
  detalhes_execucao: string;
  valor_base: number;
}

export interface ChecklistAvariasState {
  manchas_preexistentes: boolean;
  fios_puxados_ou_furos: boolean;
  desgaste_costura_ou_forro: boolean;
  botoes_ou_fechos_ausentes: boolean;
  ziper_comprometido: boolean;
}

export interface FotoComprimidaItem {
  id_temp: string;
  file: File;
  preview_url: string;
  nome_original: string;
  mime_type: string;
  tamanho_original_bytes: number;
  tamanho_comprimido_bytes: number;
  legenda_avaria: string;
}

export interface OrdemServicoCriadaPayload {
  cliente_nome: string;
  cliente_telefone: string;
  cliente_email: string;
  descricao_peca: string;
  tipo_tecido: TipoTecidoChoice;
  taxa_higienizacao_ativa: boolean;
  prazo_entrega_horas: number;
  termo_avarias_aceito: boolean;
  checklist_avarias: ChecklistAvariasState;
  observacoes_triagem: string;
  itens: Array<{
    nome_servico: string;
    detalhes_execucao: string;
    valor_base: string;
  }>;
  fotos_upload: File[];
  emitir_orcamento_imediato: boolean;
  resumo_financeiro: {
    subtotal_base: string;
    multiplicador_aplicado: string;
    subtotal_tecido: string;
    taxa_higienizacao_valor: string;
    taxa_urgencia_valor: string;
    valor_total: string;
    sinal_minimo_exigido: string;
  };
}

const emit = defineEmits<{
  (e: "os-created", payload: OrdemServicoCriadaPayload): void;
}>();

const ALLOWED_MIME_TYPES: ReadonlyArray<string> = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

const TECIDOS_COMPLEXOS: ReadonlySet<TipoTecidoChoice> = new Set([
  "COURO",
  "SEDA",
  "VELUDO",
  "PEDRARIAS",
]);

const OPCOES_TECIDO: ReadonlyArray<{
  valor: TipoTecidoChoice;
  rotulo: string;
  complexo: boolean;
}> = [
  { valor: "ALGODAO", rotulo: "Algodão (1.00x)", complexo: false },
  { valor: "JEANS", rotulo: "Jeans / Brim (1.00x)", complexo: false },
  { valor: "POLIESTER", rotulo: "Poliéster / Viscose (1.00x)", complexo: false },
  { valor: "OUTROS", rotulo: "Outros Tecidos Normais (1.00x)", complexo: false },
  { valor: "COURO", rotulo: "Couro Natural / Ecológico (1.40x)", complexo: true },
  { valor: "SEDA", rotulo: "Seda Pura / Cetim Nobre (1.40x)", complexo: true },
  { valor: "VELUDO", rotulo: "Veludo Alemão / Cristal (1.40x)", complexo: true },
  { valor: "PEDRARIAS", rotulo: "Renda / Pedrarias / Alta Costura (1.40x)", complexo: true },
];

const form = reactive({
  cliente_nome: "",
  cliente_telefone: "",
  cliente_email: "",
  descricao_peca: "",
  tipo_tecido: "SEDA" as TipoTecidoChoice,
  taxa_higienizacao_ativa: false,
  prazo_entrega_horas: 72,
  termo_avarias_aceito: false,
  observacoes_triagem: "",
  emitir_orcamento_imediato: true,
});

const checklistAvarias = reactive<ChecklistAvariasState>({
  manchas_preexistentes: false,
  fios_puxados_ou_furos: false,
  desgaste_costura_ou_forro: false,
  botoes_ou_fechos_ausentes: false,
  ziper_comprometido: false,
});

const itens = ref<ItemOrdemServicoInput[]>([
  {
    id_temp: crypto.randomUUID(),
    nome_servico: "Ajuste de Cintura e Acinturamento Lateral",
    detalhes_execucao: "Preservar costura invisível original e forro interno",
    valor_base: 95.0,
  },
]);

const novoItem = reactive({
  nome_servico: "",
  detalhes_execucao: "",
  valor_base: 45.0,
});

const fotosComprimidas = ref<FotoComprimidaItem[]>([]);
const comprimindoImagem = ref<boolean>(false);
const erroValidacao = ref<string | null>(null);
const mensagemSucesso = ref<string | null>(null);

// Arredondamento determinístico ROUND_HALF_UP para 2 casas decimais em centavos inteiros
function roundHalfUp(valor: number): number {
  const sinal = valor < 0 ? -1 : 1;
  const absoluto = Math.abs(valor);
  const centavos = Math.floor(absoluto * 100 + 0.5 + 1e-9);
  return (sinal * centavos) / 100;
}

function formatarMoeda(valor: number): string {
  return valor.toFixed(2);
}

const multiplicadorTecido = computed<number>(() => {
  return TECIDOS_COMPLEXOS.has(form.tipo_tecido) ? 1.4 : 1.0;
});

const subtotalBase = computed<number>(() => {
  const soma = itens.value.reduce((acc, item) => acc + Number(item.valor_base || 0), 0);
  return roundHalfUp(soma);
});

const subtotalTecido = computed<number>(() => {
  return roundHalfUp(subtotalBase.value * multiplicadorTecido.value);
});

const taxaHigienizacaoValor = computed<number>(() => {
  return form.taxa_higienizacao_ativa ? 35.0 : 0.0;
});

const isUrgente = computed<boolean>(() => {
  return Number(form.prazo_entrega_horas) > 0 && Number(form.prazo_entrega_horas) < 48;
});

const taxaUrgenciaValor = computed<number>(() => {
  if (!isUrgente.value) return 0.0;
  return roundHalfUp(subtotalTecido.value * 0.3);
});

const taxasAdicionais = computed<number>(() => {
  return roundHalfUp(taxaHigienizacaoValor.value + taxaUrgenciaValor.value);
});

const valorTotal = computed<number>(() => {
  return roundHalfUp(subtotalTecido.value + taxasAdicionais.value);
});

const sinalMinimoExigido = computed<number>(() => {
  if (valorTotal.value > 80.0) {
    return roundHalfUp(valorTotal.value * 0.5);
  }
  return 0.0;
});

const travaTriagemSatisfeita = computed<boolean>(() => {
  if (!form.emitir_orcamento_imediato) return true;
  return fotosComprimidas.value.length >= 1 && form.termo_avarias_aceito === true;
});

function adicionarItemServico(): void {
  erroValidacao.value = null;
  const nome = novoItem.nome_servico.trim();
  const valor = roundHalfUp(Number(novoItem.valor_base));
  if (nome.length < 3) {
    erroValidacao.value = "Informe uma descrição válida para o item de serviço (mín. 3 caracteres).";
    return;
  }
  if (isNaN(valor) || valor <= 0) {
    erroValidacao.value = "O valor base do item deve ser maior que R$ 0,00.";
    return;
  }
  itens.value.push({
    id_temp: crypto.randomUUID(),
    nome_servico: nome,
    detalhes_execucao: novoItem.detalhes_execucao.trim(),
    valor_base: valor,
  });
  novoItem.nome_servico = "";
  novoItem.detalhes_execucao = "";
  novoItem.valor_base = 45.0;
}

function removerItemServico(idTemp: string): void {
  if (itens.value.length <= 1) {
    erroValidacao.value = "A Ordem de Serviço deve manter ao menos 1 item para orçamento.";
    return;
  }
  itens.value = itens.value.filter((item) => item.id_temp !== idTemp);
}

async function processarUploadImagens(event: Event): Promise<void> {
  erroValidacao.value = null;
  const input = event.target as HTMLInputElement;
  if (!input.files || input.files.length === 0) return;

  const arquivos = Array.from(input.files);
  comprimindoImagem.value = true;

  try {
    for (const arquivoOriginal of arquivos) {
      if (!ALLOWED_MIME_TYPES.includes(arquivoOriginal.type)) {
        throw new Error(
          `Formato '${arquivoOriginal.type || "desconhecido"}' rejeitado. Use apenas JPG, PNG ou WEBP.`
        );
      }

      const opcoesCompressao = {
        maxSizeMB: 0.8,
        maxWidthOrHeight: 1600,
        useWebWorker: true,
        initialQuality: 0.82,
      };

      const blobComprimido = await imageCompression(arquivoOriginal, opcoesCompressao);
      const arquivoFinal = new File([blobComprimido], arquivoOriginal.name, {
        type: blobComprimido.type || arquivoOriginal.type,
        lastModified: Date.now(),
      });

      const previewUrl = URL.createObjectURL(arquivoFinal);

      fotosComprimidas.value.push({
        id_temp: crypto.randomUUID(),
        file: arquivoFinal,
        preview_url: previewUrl,
        nome_original: arquivoOriginal.name,
        mime_type: arquivoFinal.type,
        tamanho_original_bytes: arquivoOriginal.size,
        tamanho_comprimido_bytes: arquivoFinal.size,
        legenda_avaria: "Vistoria de recebimento no balcão",
      });
    }
  } catch (err: unknown) {
    erroValidacao.value =
      err instanceof Error ? err.message : "Falha ao comprimir a imagem selecionada.";
  } finally {
    comprimindoImagem.value = false;
    input.value = "";
  }
}

function removerFoto(idTemp: string): void {
  const alvo = fotosComprimidas.value.find((f) => f.id_temp === idTemp);
  if (alvo) {
    URL.revokeObjectURL(alvo.preview_url);
  }
  fotosComprimidas.value = fotosComprimidas.value.filter((f) => f.id_temp !== idTemp);
}

function submeterOrdemServico(): void {
  erroValidacao.value = null;
  mensagemSucesso.value = null;

  if (form.cliente_nome.trim().length < 3) {
    erroValidacao.value = "Informe o nome completo do cliente.";
    return;
  }
  if (form.cliente_telefone.trim().length < 8) {
    erroValidacao.value = "Informe um telefone/WhatsApp válido para contato.";
    return;
  }
  if (form.descricao_peca.trim().length < 4) {
    erroValidacao.value = "Descreva a peça recebida para triagem (ex.: Vestido Longo de Seda Verde).";
    return;
  }
  if (itens.value.length === 0) {
    erroValidacao.value = "Adicione ao menos 1 serviço de costura ao orçamento.";
    return;
  }

  // Validação Determinística RN-TRI-001 no Front-end antes do envio
  if (form.emitir_orcamento_imediato) {
    if (fotosComprimidas.value.length < 1) {
      erroValidacao.value =
        "Trava RN-TRI-001: Anexe ao menos 1 foto comprimida da peça para emitir o orçamento (Status ORCADA).";
      return;
    }
    if (!form.termo_avarias_aceito) {
      erroValidacao.value =
        "Trava RN-TRI-001: É obrigatório marcar o aceite do Termo de Vistoria e Avarias para transitar para ORCADA.";
      return;
    }
  }

  const payload: OrdemServicoCriadaPayload = {
    cliente_nome: form.cliente_nome.trim(),
    cliente_telefone: form.cliente_telefone.trim(),
    cliente_email: form.cliente_email.trim(),
    descricao_peca: form.descricao_peca.trim(),
    tipo_tecido: form.tipo_tecido,
    taxa_higienizacao_ativa: form.taxa_higienizacao_ativa,
    prazo_entrega_horas: Number(form.prazo_entrega_horas),
    termo_avarias_aceito: form.termo_avarias_aceito,
    checklist_avarias: { ...checklistAvarias },
    observacoes_triagem: form.observacoes_triagem.trim(),
    itens: itens.value.map((item) => ({
      nome_servico: item.nome_servico,
      detalhes_execucao: item.detalhes_execucao,
      valor_base: formatarMoeda(roundHalfUp(item.valor_base)),
    })),
    fotos_upload: fotosComprimidas.value.map((f) => f.file),
    emitir_orcamento_imediato: form.emitir_orcamento_imediato,
    resumo_financeiro: {
      subtotal_base: formatarMoeda(subtotalBase.value),
      multiplicador_aplicado: formatarMoeda(multiplicadorTecido.value),
      subtotal_tecido: formatarMoeda(subtotalTecido.value),
      taxa_higienizacao_valor: formatarMoeda(taxaHigienizacaoValor.value),
      taxa_urgencia_valor: formatarMoeda(taxaUrgenciaValor.value),
      valor_total: formatarMoeda(valorTotal.value),
      sinal_minimo_exigido: formatarMoeda(sinalMinimoExigido.value),
    },
  };

  emit("os-created", payload);
  mensagemSucesso.value = `Ordem de Serviço registrada com sucesso! Valor Total calculado: R$ ${formatarMoeda(
    valorTotal.value
  )}.`;
}
</script>

<template>
  <div class="bg-white border border-stone-200 shadow-sm p-6 md:p-10 text-stone-800">
    <div class="border-b border-stone-200 pb-6 mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <p class="text-xs uppercase tracking-[0.2em] text-stone-500 mb-2">
          RECEPÇÃO & TRIAGEM TÉCNICA
        </p>
        <h2 class="font-serif text-2xl md:text-3xl text-stone-900">
          — Abertura de Ordem de Serviço (OS)
        </h2>
      </div>
      <div class="bg-stone-100 px-4 py-2.5 border border-stone-200 text-xs text-stone-700">
        <span class="font-semibold uppercase tracking-wider block text-stone-900">
          Protocolo Determinístico
        </span>
        Arredondamento <code class="font-mono">ROUND_HALF_UP</code> • Validade de 7 dias
      </div>
    </div>

    <div
      v-if="erroValidacao"
      class="mb-6 bg-red-50 border-l-4 border-red-700 p-4 text-sm text-red-900"
      role="alert"
    >
      <p class="font-semibold">Bloqueio de Validação / Regra de Domínio</p>
      <p class="mt-1">{{ erroValidacao }}</p>
    </div>

    <div
      v-if="mensagemSucesso"
      class="mb-6 bg-emerald-50 border-l-4 border-emerald-700 p-4 text-sm text-emerald-900"
      role="status"
    >
      <p class="font-semibold">Ordem de Serviço Processada</p>
      <p class="mt-1">{{ mensagemSucesso }}</p>
    </div>

    <form @submit.prevent="submeterOrdemServico" class="space-y-8">
      <!-- 1. Dados do Cliente e da Peça -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label class="block text-xs uppercase tracking-wider text-stone-600 mb-2">
            Nome Completo do Cliente *
          </label>
          <input
            v-model="form.cliente_nome"
            type="text"
            required
            placeholder="Ex.: Mariana Vasconcelos"
            class="w-full border border-stone-300 px-4 py-2.5 text-sm focus:border-stone-900 focus:outline-none"
          />
        </div>

        <div>
          <label class="block text-xs uppercase tracking-wider text-stone-600 mb-2">
            Telefone / WhatsApp *
          </label>
          <input
            v-model="form.cliente_telefone"
            type="tel"
            required
            placeholder="(31) 99876-5432"
            class="w-full border border-stone-300 px-4 py-2.5 text-sm focus:border-stone-900 focus:outline-none"
          />
        </div>

        <div>
          <label class="block text-xs uppercase tracking-wider text-stone-600 mb-2">
            Descrição da Peça Recebida *
          </label>
          <input
            v-model="form.descricao_peca"
            type="text"
            required
            placeholder="Ex.: Vestido Midi em Seda Pura Off-White"
            class="w-full border border-stone-300 px-4 py-2.5 text-sm focus:border-stone-900 focus:outline-none"
          />
        </div>

        <div>
          <label class="block text-xs uppercase tracking-wider text-stone-600 mb-2">
            Classificação de Tecido (`tipo_tecido`) *
          </label>
          <select
            v-model="form.tipo_tecido"
            class="w-full border border-stone-300 px-4 py-2.5 text-sm bg-white focus:border-stone-900 focus:outline-none"
          >
            <option
              v-for="opcao in OPCOES_TECIDO"
              :key="opcao.valor"
              :value="opcao.valor"
            >
              {{ opcao.rotulo }}
            </option>
          </select>
        </div>
      </div>

      <!-- 2. Parâmetros de Prazo e Higienização -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 bg-stone-50 p-5 border border-stone-200">
        <div>
          <label class="block text-xs uppercase tracking-wider text-stone-600 mb-2">
            Prazo de Entrega Estimado (Horas) *
          </label>
          <div class="flex items-center gap-3">
            <input
              v-model.number="form.prazo_entrega_horas"
              type="number"
              min="1"
              max="720"
              class="w-32 border border-stone-300 px-3 py-2 text-sm bg-white"
            />
            <span
              v-if="isUrgente"
              class="text-xs font-semibold px-2.5 py-1 bg-amber-100 text-amber-900 border border-amber-300"
            >
              URGÊNCIA (&lt; 48h): +30% sobre Subtotal Tecido
            </span>
            <span v-else class="text-xs text-stone-500">
              Prazo regular (sem acréscimo de urgência)
            </span>
          </div>
        </div>

        <div class="flex items-center">
          <label class="flex items-start gap-3 cursor-pointer">
            <input
              v-model="form.taxa_higienizacao_ativa"
              type="checkbox"
              class="mt-1 h-4 w-4 accent-stone-900"
            />
            <span class="text-sm text-stone-800">
              <strong class="block font-medium">Incluir Taxa de Higienização (+ R$ 35,00)</strong>
              <span class="text-xs text-stone-500">
                Higienização técnica pré-costura e vaporização final de entrega.
              </span>
            </span>
          </label>
        </div>
      </div>

      <!-- 3. Itens de Serviço -->
      <div>
        <h3 class="text-xs uppercase tracking-[0.18em] text-stone-500 mb-4">
          ITENS DO ORÇAMENTO (`itens`)
        </h3>

        <div class="space-y-2 mb-4">
          <div
            v-for="item in itens"
            :key="item.id_temp"
            class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-stone-50 border border-stone-200 px-4 py-3"
          >
            <div>
              <p class="text-sm font-medium text-stone-900">{{ item.nome_servico }}</p>
              <p v-if="item.detalhes_execucao" class="text-xs text-stone-500">
                {{ item.detalhes_execucao }}
              </p>
            </div>
            <div class="flex items-center gap-4">
              <span class="text-sm font-mono font-semibold text-stone-900">
                R$ {{ formatarMoeda(item.valor_base) }}
              </span>
              <button
                type="button"
                @click="removerItemServico(item.id_temp)"
                class="text-xs text-red-700 hover:underline uppercase tracking-wider"
              >
                Remover
              </button>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-12 gap-3 bg-stone-100/70 p-4 border border-stone-200">
          <div class="sm:col-span-5">
            <input
              v-model="novoItem.nome_servico"
              type="text"
              placeholder="Novo serviço (ex.: Bainha Invisível)"
              class="w-full border border-stone-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div class="sm:col-span-4">
            <input
              v-model="novoItem.detalhes_execucao"
              type="text"
              placeholder="Observação técnica"
              class="w-full border border-stone-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div class="sm:col-span-2">
            <input
              v-model.number="novoItem.valor_base"
              type="number"
              step="0.50"
              min="1"
              class="w-full border border-stone-300 px-3 py-2 text-sm bg-white"
            />
          </div>
          <div class="sm:col-span-1">
            <button
              type="button"
              @click="adicionarItemServico"
              class="w-full h-full bg-stone-900 text-white text-xs uppercase tracking-wider py-2 px-3 hover:bg-stone-700"
            >
              +
            </button>
          </div>
        </div>
      </div>

      <!-- 4. Checklist Obrigatório de Avarias e Upload com Compressão Local -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-stone-200 pt-6">
        <div>
          <h3 class="text-xs uppercase tracking-[0.18em] text-stone-500 mb-3">
            CHECKLIST DE VISTORIA E AVARIAS (`RN-TRI-001`)
          </h3>
          <div class="space-y-2.5 bg-stone-50 p-4 border border-stone-200 text-sm">
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input
                v-model="checklistAvarias.manchas_preexistentes"
                type="checkbox"
                class="h-4 w-4 accent-stone-900"
              />
              <span>Manchas ou desbotamento pré-existentes no tecido</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input
                v-model="checklistAvarias.fios_puxados_ou_furos"
                type="checkbox"
                class="h-4 w-4 accent-stone-900"
              />
              <span>Fios puxados, puídos ou microfuros na malha/seda</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input
                v-model="checklistAvarias.desgaste_costura_ou_forro"
                type="checkbox"
                class="h-4 w-4 accent-stone-900"
              />
              <span>Esgarçamento na costura interna ou forro danificado</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input
                v-model="checklistAvarias.botoes_ou_fechos_ausentes"
                type="checkbox"
                class="h-4 w-4 accent-stone-900"
              />
              <span>Botões, colchetes ou pedrarias ausentes/soltos</span>
            </label>
            <label class="flex items-center gap-2.5 cursor-pointer">
              <input
                v-model="checklistAvarias.ziper_comprometido"
                type="checkbox"
                class="h-4 w-4 accent-stone-900"
              />
              <span>Cursor ou dentes do zíper com travamento</span>
            </label>
          </div>

          <div class="mt-4">
            <label class="block text-xs uppercase tracking-wider text-stone-600 mb-1.5">
              Observações de Triagem (`observacoes_triagem`)
            </label>
            <textarea
              v-model="form.observacoes_triagem"
              rows="2"
              placeholder="Descreva o estado geral da peça no ato da recepção..."
              class="w-full border border-stone-300 p-3 text-sm focus:border-stone-900 focus:outline-none"
            ></textarea>
          </div>

          <label
            class="mt-4 flex items-start gap-3 p-3.5 border border-stone-300 bg-amber-50/60 cursor-pointer"
          >
            <input
              v-model="form.termo_avarias_aceito"
              type="checkbox"
              class="mt-1 h-4 w-4 accent-stone-900"
            />
            <span class="text-xs text-stone-800 leading-relaxed">
              <strong class="block text-stone-900 uppercase tracking-wider">
                Aceite Obrigatório (`termo_avarias_aceito = True`)
              </strong>
              Confirmo que a peça foi vistoriada na presença do cliente e que o checklist
              e fotos anexadas refletem fielmente seu estado de entrada (RN-TRI-001).
            </span>
          </label>
        </div>

        <!-- Upload com browser-image-compression -->
        <div>
          <h3 class="text-xs uppercase tracking-[0.18em] text-stone-500 mb-3">
            FOTOS DA PEÇA COM COMPRESSÃO LOCAL (`browser-image-compression`)
          </h3>
          <div class="border-2 border-dashed border-stone-300 p-5 text-center bg-stone-50">
            <input
              id="os-foto-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              @change="processarUploadImagens"
              class="hidden"
            />
            <label
              for="os-foto-input"
              class="inline-block bg-stone-900 text-white text-xs uppercase tracking-widest px-5 py-2.5 cursor-pointer hover:bg-stone-700"
            >
              {{ comprimindoImagem ? "Comprimindo Imagem..." : "Selecionar Fotos da Peça +" }}
            </label>
            <p class="text-xs text-stone-500 mt-2">
              Compressão client-side automática (máx. 800KB / 1600px • JPEG, PNG, WEBP)
            </p>
          </div>

          <div v-if="fotosComprimidas.length > 0" class="mt-4 space-y-2.5">
            <div
              v-for="foto in fotosComprimidas"
              :key="foto.id_temp"
              class="flex items-center justify-between gap-3 border border-stone-200 p-2.5 bg-white"
            >
              <div class="flex items-center gap-3">
                <img
                  :src="foto.preview_url"
                  :alt="foto.nome_original"
                  class="w-12 h-12 object-cover border border-stone-200"
                />
                <div class="text-xs">
                  <p class="font-medium text-stone-900 truncate max-w-[180px]">
                    {{ foto.nome_original }}
                  </p>
                  <p class="text-stone-500">
                    {{ (foto.tamanho_original_bytes / 1024).toFixed(1) }} KB →
                    <strong class="text-emerald-700">
                      {{ (foto.tamanho_comprimido_bytes / 1024).toFixed(1) }} KB
                    </strong>
                  </p>
                </div>
              </div>
              <button
                type="button"
                @click="removerFoto(foto.id_temp)"
                class="text-xs text-red-700 hover:underline uppercase"
              >
                Excluir
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 5. Resumo Financeiro Determinístico -->
      <div class="bg-stone-900 text-stone-100 p-6 md:p-8">
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm border-b border-stone-700 pb-5">
          <div>
            <span class="text-xs uppercase tracking-wider text-stone-400 block">
              Subtotal Base
            </span>
            <span class="font-mono text-lg">R$ {{ formatarMoeda(subtotalBase) }}</span>
          </div>
          <div>
            <span class="text-xs uppercase tracking-wider text-stone-400 block">
              Multiplicador Tecido
            </span>
            <span class="font-mono text-lg">{{ formatarMoeda(multiplicadorTecido) }}x</span>
          </div>
          <div>
            <span class="text-xs uppercase tracking-wider text-stone-400 block">
              Subtotal Tecido
            </span>
            <span class="font-mono text-lg">R$ {{ formatarMoeda(subtotalTecido) }}</span>
          </div>
          <div>
            <span class="text-xs uppercase tracking-wider text-stone-400 block">
              Taxas Adicionais
            </span>
            <span class="font-mono text-lg">R$ {{ formatarMoeda(taxasAdicionais) }}</span>
          </div>
          <div>
            <span class="text-xs uppercase tracking-wider text-amber-300 block">
              Valor Total Final
            </span>
            <span class="font-mono text-2xl font-bold text-white">
              R$ {{ formatarMoeda(valorTotal) }}
            </span>
          </div>
        </div>

        <div class="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div class="text-xs text-stone-300">
            <span v-if="sinalMinimoExigido > 0">
              <strong>Trava RN-FIN-001 Ativa:</strong> Exige sinal mínimo de 50% (R$
              {{ formatarMoeda(sinalMinimoExigido) }}) para iniciar costura.
            </span>
            <span v-else>
              Orçamento até R$ 80,00: dispensado de sinal mínimo obrigatório (RN-FIN-001).
            </span>
          </div>

          <button
            type="submit"
            :disabled="!travaTriagemSatisfeita"
            class="bg-white text-stone-900 px-6 py-3 text-xs uppercase tracking-widest font-semibold hover:bg-stone-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Registrar OS & Emitir Orçamento +
          </button>
        </div>
      </div>
    </form>
  </div>
</template>
