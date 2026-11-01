# Ateliê da Belinha — Alta Costura & Sistema de Gestão de Ordens de Serviço (OS)

![Status](https://img.shields.io/badge/Status-Produção-ec4899?style=for-the-badge)
![Django](https://img.shields.io/badge/Django_5.x-092E20?style=for-the-badge&logo=django&logoColor=white)
![Vue.js](https://img.shields.io/badge/Vue_3-4FC08D?style=for-the-badge&logo=vuedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Vercel](https://img.shields.io/badge/Deploy-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

Plataforma web editorial e sistema de gestão de **Ordens de Serviço (OS)** desenvolvido para o **Ateliê da Belinha**, combinando identidade visual de alta costura com engenharia de software orientada ao domínio (**Clean Architecture** e **Domain-Driven Design — DDD**).

---

## Sumário

- [Visão Geral](#-visão-geral)
- [Principais Funcionalidades](#-principais-funcionalidades)
- [Regras de Domínio e Máquina de Estados](#-regras-de-domínio-e-máquina-de-estados)
- [Fórmula de Precificação Determinística](#-fórmula-de-precificação-determinística)
- [Arquitetura e Estrutura do Repositório](#-arquitetura-e-estrutura-do-repositório)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Como Executar Localmente](#-como-executar-localmente)
- [Deploy na Vercel](#-deploy-na-vercel)
- [Licença](#-licença)

---

## Visão Geral

O projeto reúne em uma única entrega:

1. **Aplicação Web Interativa Autocontida (`index.html`)**: Portal institucional multipáginas com estética editorial (paleta Rosa Pastel, Azul Celeste e Branco com tipografia caligráfica clássica), simulador completo de abertura de Ordens de Serviço, compressão client-side de fotos de triagem e quadro de comando com máquina de estados em tempo real.
2. **Core de Domínio Backend (`backend/`)**: Implementação de referência em **Python 3.12 / Django 5 + Django REST Framework** com precisão monetária `Decimal` (`ROUND_HALF_UP`), `CheckConstraints` de banco de dados, bloqueio pessimista (`select_for_update`) e auditoria de transições.
3. **Componente Frontend Modular (`frontend/`)**: Implementação em **Vue 3 (`<script setup lang="ts">`)** integrada com `browser-image-compression` para otimização de imagens antes do envio.

---

## Principais Funcionalidades

- **Catálogo e Abertura de OS**: Seleção dinâmica de serviços de ajuste e alta costura, classificação por tipo de tecido e cálculo de orçamento em tempo real.
- **Triagem Fotográfica Obrigatória com Compressão Client-Side**: Upload e inspeção de fotos da peça com compressão automática no navegador (`WebP/JPEG`, limite de 5 MB por imagem) e aceite formal do Termo de Avarias.
- **Máquina de Estados Finita (FSM) com Guard Clauses**: Controle rigoroso de transição entre os estágios da Ordem de Serviço, bloqueando avanços que violem regras financeiras ou de triagem (retornando exceções de negócio semânticas `HTTP 422 / 409`).
- **Gestão Financeira e Quitação**: Registro incremental de pagamentos (sinal de 50% e quitação de saldo remanescente) com prevenção de pagamento excedente ou em OS cancelada.
- **Histórico e Auditoria**: Rastreamento completo das mudanças de status com carimbo de tempo e justificativa.

---

## Regras de Domínio e Máquina de Estados

### Fluxo de Estados (`StatusOS`)

```text
CRIADA ──► ORCADA ──► APROVADA ──► EM_COSTURA ──► PRONTA_PARA_PROVA ──► PRONTA_PARA_RETIRADA ──► FINALIZADA
  │          │           │             ▲                  │
  ▼          ▼           ▼             └──────────────────┘
CANCELADA  CANCELADA  CANCELADA
```

### Travas de Negócio (Guard Clauses)

| Código | Transição Alvo | Regra de Domínio | Status HTTP |
| :--- | :--- | :--- | :---: |
| **`RN-ORC-001`** | Cálculo de Orçamento | A Ordem de Serviço deve conter ao menos **1 item de serviço** selecionado. | `400` |
| **`RN-TRI-001`** | `CRIADA` → `ORCADA` | **Trava de Avaria**: Exige no mínimo **1 registro fotográfico** de inspeção e aceite do termo de vistoria (`termo_avarias_aceito = True`). Define validade do orçamento em 7 dias. | `422` |
| **`RN-FIN-001`** | `APROVADA` → `EM_COSTURA` | **Trava de Início**: Para orçamentos com valor total acima de **R$ 80,00**, exige o pagamento mínimo de **50% de sinal** antes de iniciar a costura na bancada. | `422` |
| **`RN-FIN-002`** | `PRONTA_PARA_RETIRADA` → `FINALIZADA` | **Trava de Despacho/Entrega**: Bloqueia a finalização e entrega da peça caso exista **saldo devedor pendente** (`valor_pago < valor_total`). | `422` |
| **`RN-FSM-INVALID`** | Qualquer transição não mapeada | Impede saltos de etapas fora do grafo oficial da Máquina de Estados. | `409` |

---

## Fórmula de Precificação Determinística

Todos os cálculos financeiros utilizam aritmética decimal exata (`Decimal` com arredondamento `ROUND_HALF_UP` em duas casas decimais):

1. **Subtotal Base**: Soma dos valores base dos itens de serviço selecionados.
2. **Multiplicador de Complexidade do Tecido**:
   - **Tecidos Simples (`1.00x`)**: Algodão, Jeans, Poliéster e Outros.
   - **Tecidos Complexos/Nobres (`1.40x`)**: Couro Natural/Sintético, Seda Pura, Veludo e Renda/Pedrarias/Bordados.
3. **Subtotal com Tecido**: `Subtotal Base × Multiplicador`
4. **Taxas Adicionais**:
   - **Taxa de Higienização Prévio-Costura**: **+ R$ 35,00** (fixa, quando aplicável).
   - **Taxa de Urgência (Expressa)**: **+ 30%** sobre o `Subtotal com Tecido` quando o prazo de entrega solicitado for inferior a **48 horas**.
5. **Valor Total da OS**: `Subtotal com Tecido + Taxa de Higienização + Taxa de Urgência`
6. **Sinal Mínimo Exigido**: `50% do Valor Total` (se `Valor Total > R$ 80,00`) ou `R$ 0,00` (se `Valor Total <= R$ 80,00`).

---

## Arquitetura e Estrutura do Repositório

```text
atelie-da-belinha-vercel-github/
├── backend/
│   ├── apps/ordens/
│   │   ├── models.py          # Entidades Django 5 ORM (UUID, Decimal, CheckConstraints, Enums)
│   │   ├── services.py        # Service Layer: Máquina de Estados, Cálculo Determinístico e Travas RN
│   │   ├── serializers.py     # Validação de Payload, MIME Types e Criação Transacional DRF
│   │   └── views.py           # OrdemServicoViewSet com endpoints REST de transição e pagamento
│   └── requirements.txt       # Dependências Python 3.12 / Django 5.1 / DRF / Pillow
├── frontend/
│   ├── src/components/
│   │   └── OSCreateForm.vue   # Componente Vue 3 (<script setup lang="ts">) + compressão de imagem
│   ├── package.json           # Manifesto de dependências Frontend (Vue 3, Pinia, Tailwind, Vite)
│   └── vite.config.ts         # Configuração do bundler Vite
├── public/
│   └── images/                # Ativos fotográficos editoriais de alta resolução
├── index.html                 # Aplicação Web Completa (SPA autocontida pronta para produção)
├── vercel.json                # Configuração de roteamento, rewrites e cache para deploy na Vercel
├── LICENSE                    # Licença do projeto
└── README.md                  # Documentação oficial
```

---

## Tecnologias Utilizadas

- **Frontend & UI Editorial**: HTML5 Semântico, Tailwind CSS, JavaScript ES2023+, Vue 3 (`Composition API` + `TypeScript`), `browser-image-compression`, Google Fonts (*Pinyon Script*, *Great Vibes* e *Inter*).
- **Backend Core**: Python 3.12, Django 5.1, Django REST Framework (DRF), Pillow.
- **Infraestrutura & Deploy**: GitHub, Vercel (Static Hosting + Edge Rewrites + Immutable Asset Caching).

---

## Como Executar Localmente

Como a aplicação principal em `index.html` é autocontida, você pode executá-la diretamente com qualquer servidor estático local:

```bash
# 1. Clone o repositório
git clone https://github.com/DungeonMaster616/Projeto-de-um-Ateli-.git
cd Projeto-de-um-Ateli-

# 2. Inicie um servidor HTTP local (exemplo com Python ou Node.js)
python -m http.server 8080
# ou
npx serve .
```

Em seguida, acesse `http://localhost:8080` no navegador.

---

## Deploy na Vercel

O repositório já está configurado com o arquivo `vercel.json` otimizado para deploy imediato:

1. Faça push do repositório para o seu **GitHub**:
   ```bash
   git add .
   git commit -m "docs: update professional README and Vercel config"
   git push origin main
   ```
2. Acesse [vercel.com/new](https://vercel.com/new) e importe o repositório.
3. Mantenha o **Framework Preset** como **Other** (as configurações de `rewrites`, `cleanUrls` e `headers` do `vercel.json` serão aplicadas automaticamente).
4. Clique em **Deploy**.

---

## Licença

Distribuído sob a licença constante no arquivo [LICENSE](./LICENSE).
