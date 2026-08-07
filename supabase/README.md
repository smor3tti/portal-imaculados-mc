# Banco de dados no Supabase

Estrutura montada a partir da **Ficha cadastral membros** oficial do clube.

---

## Instalação (uns 15 minutos)

### 1. Criar o projeto
[supabase.com](https://supabase.com) → **New project**

- **Region:** `South America (São Paulo)` — deixa o portal mais rápido daqui
- **Database password:** guarde num gerenciador de senhas; você vai precisar dela

O plano gratuito dá 500 MB e 1 GB de arquivos: sobra para o clube inteiro.

### 2. Criar as tabelas
**SQL Editor → New query** → cole todo o `01-schema.sql` → **Run**

Vão aparecer avisos do tipo *"trigger ... does not exist, skipping"*. É normal —
são os comandos de limpeza rodando num banco vazio.

### 3. Importar os integrantes que já responderam a ficha

**3.1** No Google Forms → aba **Respostas** → ícone verde do Sheets
**3.2** Na planilha → **Arquivo → Fazer download → CSV**
**3.3** No Supabase, rode a **Parte 1** do `02-importar-ficha.sql` (cria a área de recepção)
**3.4** **Table Editor** → tabela `importacao_ficha` → **Insert → Import data from CSV**
**3.5** Rode a **Parte 2** (conferência) e leia o resultado
**3.6** Rode a **Parte 3 e 4** (importação de verdade)

> A importação pode ser rodada **mais de uma vez** sem duplicar ninguém: quem já
> existe é atualizado. Se novas pessoas responderem a ficha depois, é só repetir.

### 4. Criar o primeiro acesso
**Authentication → Users → Add user** com o seu e-mail. Depois, no SQL Editor:

```sql
-- troque o e-mail pelo seu e o nome pelo seu nome na tabela integrantes
insert into public.perfis (user_id, integrante_id, cargo)
select u.id, i.id, 'Presidente'
  from auth.users u, public.integrantes i
 where u.email = 'seu-email@exemplo.com'
   and i.nome_completo = 'Seu Nome Completo';
```

A partir daí você entra no portal e cria os demais acessos pela aba **Acessos**.

---

## Como os dados ficam organizados

| Tabela | O que guarda |
|---|---|
| `integrantes` | Os campos da ficha (nome, colete, função, moto, padrinho...) |
| `integrantes_dados_sensiveis` | **Endereço e nº da CNH**, com acesso restrito |
| `perfis` | Liga o login ao integrante e define cargo e permissões |
| `cargos` | As 12 funções oficiais, cada uma com suas permissões padrão |
| `mensalidades` / `caixa` | Financeiro, com lançamento automático no caixa |
| `eventos` / `presencas` | Agenda e lista de presença |
| `comunicados` / `documentos` | Avisos e arquivos |
| `solicitacoes_cadastro` | Pedidos de ingresso vindos do site |

---

## Três decisões de projeto que valem explicação

### 1. Senhas não ficam no nosso banco
Quem cuida disso é o **Supabase Auth**: hash forte, recuperação por e-mail,
proteção contra tentativas repetidas. Bem mais seguro do que qualquer coisa que
guardássemos por conta própria — e resolve o problema que existia na versão com
planilha do Google.

### 2. CNH e endereço ficam numa tabela separada
O controle de acesso do Postgres filtra **linhas**, não **colunas**. Se a CNH
estivesse junto com o resto, qualquer integrante que pudesse ver a lista veria
também o documento de todo mundo. Numa tabela à parte, só quem tem a permissão
`ver_dados_sensiveis` enxerga — hoje: Presidente, Vice, Diretor Geral, Diretor
Disciplina e Secretário.

### 3. Nenhuma política usa `FOR ALL`
As permissões de escrita são declaradas uma a uma (inserir, atualizar, excluir).
Motivo: no Postgres, `FOR ALL` **também vale para leitura**, e as políticas se
somam. Alguém com permissão de editar o financeiro continuaria lendo tudo mesmo
que você bloqueasse a leitura dele individualmente. Isso foi encontrado e
corrigido durante os testes.

---

## O que foi testado antes de entregar

Rodei o schema num PostgreSQL 16 de verdade, simulando o ambiente do Supabase:

- Presidente vê os 3 integrantes, dados sensíveis e financeiro
- Tesoureiro vê a lista e o financeiro, mas **só o próprio** endereço e CNH
- Próspero vê **apenas o próprio cadastro** e a própria mensalidade
- Próspero tentando editar outro integrante: **bloqueado**
- Liberar `ver_dados_sensiveis` individualmente ao Tesoureiro: passa a ver os 3
- Bloquear `ver_financeiro` individualmente: volta a ver só a própria mensalidade,
  **mas continua conseguindo lançar** (ainda tem `editar_financeiro`)
- Visitante sem login **consegue enviar** ficha de ingresso e **não consegue ler** nenhuma
- Pagar mensalidade lança R$ 40,00 no caixa automaticamente
- Mudar o cargo do integrante muda o acesso dele junto
- Cobrar o mesmo mês duas vezes: **bloqueado**

A importação foi testada com dados propositalmente bagunçados — data inválida,
cargo em minúsculo, "Membro com Brasao" sem acento, linha em branco, placa
minúscula, campos vazios. Todos foram tratados: cargos normalizados, datas
convertidas nos dois formatos (MM/DD e DD/MM), placas em maiúsculo, linha vazia
ignorada e padrinhos ligados automaticamente pelo nome ou pelo colete.

---

## Ajuste necessário no portal

Os cargos da ficha **não são os que estão no portal hoje**. A ficha tem 12
funções (incluindo Conselheiro, Secretário, Imprensa/Marketing e Membro com
Brasão); o portal tem 7. O banco já usa a lista da ficha — falta atualizar a
interface para a mesma lista, além dos novos campos (padrinho, veículo, CNH).

## Segurança — pontos de atenção

- **A CNH é dado pessoal sensível.** Só cadastre se o clube realmente precisar,
  e avise os integrantes de que ela está guardada e quem tem acesso.
- **Guarde a senha do banco** num gerenciador de senhas, não em anotação.
- **Nunca coloque a `service_role key` no site.** Essa chave ignora todas as
  regras de segurança. No portal use apenas a `anon key`.
- **Backups:** o plano gratuito não faz backup automático. Exporte periodicamente
  em *Database → Backups*, ou considere o plano pago quando houver dados reais.

---

## Portal conectado (feito)

O site já aponta para este banco. Detalhes de como funciona:

**Login** — o portal usa o Supabase Auth. Cada integrante entra com **e-mail e senha
própria**; ninguém, nem a diretoria, consegue ver a senha de outra pessoa.

**Primeiro acesso** — a pessoa clica em "Primeiro acesso" e cadastra uma senha
usando **o mesmo e-mail da ficha**. Um gatilho no banco encontra o integrante
por esse e-mail e libera o acesso automaticamente, já com o cargo correto.
Quem se cadastra com um e-mail que não está em nenhuma ficha entra **inativo**,
e precisa ser liberado manualmente na aba Acessos.

**Esqueci a senha** — envia link de redefinição por e-mail. Na aba Acessos, o
botão de "resetar senha" também dispara esse mesmo link, em vez de gerar uma
senha temporária: com a chave pública não é possível (nem desejável) definir a
senha de outra pessoa.

**Chave usada no site** — a `publishable key`, que é pública por natureza e não
dá acesso a nada sozinha: quem decide o que cada um vê são as políticas de
segurança do banco. A `service_role key` **nunca** deve ir para o site.

### Um cuidado que rendeu correção

Vários módulos do portal verificavam apenas se havia uma "URL de API" configurada
para decidir se buscavam dados reais. No modo Supabase esse campo fica vazio, e o
resultado era o dashboard e as solicitações exibindo **dados fictícios mesmo
conectados ao banco** — sem erro visível. Foi corrigido com uma verificação única
(`temBackend()`) usada em todos os módulos.
