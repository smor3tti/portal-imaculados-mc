# Portal Imaculados M.C.

Sistema de gestão para motoclube — MVP (Fase 3: estrutura inicial de código).

## Estrutura
```
Portal_Imaculados_MC/
├── backend/        API (FastAPI + PostgreSQL/SQLite + JWT)
├── admin_pc/       App administrativo desktop (PySide6, tema preto/dourado)
├── app_mobile/     PWA (fase futura)
└── assets/         Brasão e ícones
```

## Como rodar (desenvolvimento)

### 1) Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # já vem configurado com SQLite p/ testes locais
python criar_admin.py         # cria o usuário presidente/imaculados123
uvicorn main:app --reload
```
A API sobe em `http://127.0.0.1:8000` (docs interativos em `/docs`).

### 2) App Desktop
```bash
cd admin_pc
pip install PySide6 requests
python app.py
```
Login de teste: **presidente** / **imaculados123**

## O que já está pronto (MVP)
- ✅ Estrutura de pastas completa
- ✅ Backend: models (Usuário, Integrante, Mensalidade, Evento, Caixa), auth JWT, rota de login, rota de dashboard, CRUD básico de integrantes
- ✅ App desktop: tela de login com brasão e tema preto/dourado, dashboard com sidebar e cards conectados à API

## Próximos passos sugeridos
- Telas de Cadastro de Membros, Mensalidades, Caixa e Eventos no app desktop
- Geração de PDFs (ReportLab) e gráficos (Matplotlib) nos relatórios
- Integração com WhatsApp para lembretes de mensalidade
- Integração Pix para registro automático de pagamentos
- Empacotar o app desktop como instalador Windows (.exe)
