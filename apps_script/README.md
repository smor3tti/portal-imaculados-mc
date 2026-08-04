# Usar uma planilha do Google como banco de dados

Este é o caminho **sem custo e sem servidor**: sua planilha guarda os dados e o
Google Apps Script publica um endereço que o portal consome.

```
Site (GitHub Pages)  →  Apps Script  →  Planilha do Google
      grátis              grátis            já existe
```

---

## Passo a passo (leva uns 10 minutos)

### 1. Abrir o editor de script
Na sua planilha de integrantes: **Extensões → Apps Script**.

### 2. Colar o código
Apague o conteúdo do arquivo que aparece e cole **todo** o conteúdo de `Codigo.gs`.

### 3. Trocar o segredo das senhas
Logo no começo do arquivo, troque esta linha por um texto secreto seu:

```javascript
var SENHA_SALT = 'imaculados-mc-salt';
```

Não é opcional: esse texto é o que dificulta a leitura das senhas caso alguém
tenha acesso indevido à planilha. Escolha algo aleatório e não compartilhe.

### 4. Preparar as abas
No menu suspenso de funções, escolha **`prepararPlanilha`** e clique em **Executar**.

Na primeira vez o Google vai pedir autorização — é normal, é o seu próprio
script pedindo permissão para mexer na sua planilha. Aceite.

Isso cria as abas que faltarem (`Integrantes`, `Usuarios`, `Mensalidades`,
`Eventos`, `Presencas`, `Comunicados`, `Solicitacoes`, `Caixa`, `Sessoes`) e o
primeiro acesso. **Nada do que já existe é apagado.**

> Confira em **Execuções** (menu lateral) o login e a senha criados:
> `presidente` / `imaculados123`. **Troque essa senha assim que entrar.**

### 5. Publicar
**Implantar → Nova implantação → engrenagem → App da Web**

| Campo | Valor |
|---|---|
| Executar como | **Eu** |
| Quem pode acessar | **Qualquer pessoa** |

Clique em **Implantar** e copie a URL gerada (termina em `/exec`).

> "Qualquer pessoa" assusta, mas é necessário: o site precisa conseguir falar
> com o script sem que o visitante tenha conta Google. Quem controla o que cada
> pessoa vê é o login do portal, não essa configuração.

### 6. Conectar o portal
Abra o portal, faça login, e cole a URL no campo **"URL da API"** no topo do
painel. Pronto — a partir daí tudo que você fizer grava na planilha.

---

## Encaixando seus dados atuais

Se sua planilha já tem os integrantes numa aba com outro nome ou outras colunas:

**Opção A (mais simples):** copie e cole seus dados na aba `Integrantes` criada
pelo script, encaixando nas colunas correspondentes. A coluna `id` precisa ter
números únicos (1, 2, 3...).

**Opção B:** renomeie suas colunas para bater com os nomes esperados:

```
id | nome | apelido | cargo | status | telefone | email | data_nascimento
   | data_entrada | moto_modelo | moto_placa | tipo_sanguineo
   | contato_emergencia | observacoes
```

Colunas a mais na sua planilha não atrapalham — o script ignora o que não conhece.

**Cargos aceitos:** Presidente, Vice-Presidente, Diretor, Tesoureiro, Disciplina,
Integrante, Prospero.
**Status:** Ativo ou Inativo.

---

## Dando acesso aos integrantes

Os integrantes que vieram da sua planilha ainda não têm login. Para criar:
portal → aba **Acessos** → cada pessoa recebe login e senha temporária que você
repassa. Quem entra pelo formulário público do site já ganha acesso automático
ao ser aprovado.

---

## O que muda em relação à API própria

| | Planilha (Apps Script) | API própria (FastAPI) |
|---|---|---|
| Custo | Zero | Hospedagem paga |
| Manutenção | Nenhuma | Sua |
| Envio de documentos | Não disponível | Completo |
| Segurança das senhas | Razoável (SHA-256) | Forte (bcrypt) |
| Velocidade | Boa até ~200 integrantes | Escala bem além disso |

O backend FastAPI continua no repositório, pronto para quando fizer sentido migrar.

---

## Sobre segurança — leia antes de decidir

- **Quem tem acesso de edição à planilha vê tudo**, inclusive as senhas
  embaralhadas. Compartilhe a planilha só com quem realmente precisa.
- As senhas são guardadas embaralhadas (SHA-256 + o seu segredo), não em texto
  puro. Ainda assim, isso é mais fraco que um banco de dados de verdade.
- **Não guarde documentos digitalizados, CPF ou dados sensíveis** nessa planilha.
  Para esse tipo de informação, vale hospedar a API própria.
- Faça cópias periódicas: **Arquivo → Fazer uma cópia**.
