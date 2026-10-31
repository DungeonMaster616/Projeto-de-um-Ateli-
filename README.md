# Ateliê da Belinha — Site Editorial & Core de Domínio (OS)

Projeto completo desenvolvido conforme especificação formal de Engenharia de Software (Clean Architecture + DDD) e design editorial inspirado no layout de referência **Jólly House**.

## Estrutura do Repositório

```text
├── backend/
│   ├── apps/ordens/
│   │   ├── models.py          # Entidades Django 5 ORM (UUID, Decimal, CheckConstraints, Enums)
│   │   ├── services.py        # Máquina de Estados + Cálculo Determinístico (ROUND_HALF_UP) + Travas RN
│   │   ├── serializers.py     # Validação de Payload, MIME Types e Criação Transacional DRF
│   │   └── views.py           # OrdemServicoViewSet com endpoints de transição e pagamento
│   └── requirements.txt       # Dependências Python 3.12 / Django 5.x
├── frontend/
│   └── src/components/
│       └── OSCreateForm.vue   # Componente Vue 3 (<script setup lang="ts">) + browser-image-compression
├── public/images/             # Ativos fotográficos editoriais extraídos do layout base
├── index.html                 # Aplicação Web Completa pronta para deploy imediato na Vercel / GitHub Pages
├── vercel.json                # Configuração de Deploy na Vercel
└── package.json               # Manifesto do projeto para integração GitHub -> Vercel
```

## Como Hospedar no GitHub + Vercel (Passo a Passo)

### Opção 1: Deploy Instantâneo na Vercel via GitHub
1. Crie um novo repositório no **GitHub** (ex.: `atelie-da-belinha`).
2. Extraia o conteúdo deste arquivo `.zip` na pasta do seu projeto e envie para o GitHub:
   ```bash
   git init
   git add .
   git commit -m "feat: implement Atelie da Belinha domain core and editorial website"
   git branch -M main
   git remote add origin https://github.com/SEU-USUARIO/atelie-da-belinha.git
   git push -u origin main
   ```
3. Acesse [vercel.com/new](https://vercel.com/new), conecte sua conta do GitHub e clique em **Import** no repositório `atelie-da-belinha`.
4. Clique em **Deploy** — o projeto já inclui `index.html` autocontido e configuração pronta para servir imediatamente em produção!
