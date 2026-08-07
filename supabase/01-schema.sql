-- ============================================================================
-- PORTAL IMACULADOS M.C. — Banco de dados (Supabase / PostgreSQL)
-- ============================================================================
-- Estrutura baseada na "Ficha cadastral membros" oficial do clube.
--
-- COMO USAR:
--   1. No Supabase, abra SQL Editor → New query
--   2. Cole este arquivo inteiro e clique em RUN
--   3. Confira em Table Editor se as tabelas apareceram
--
-- DECISÕES DE PROJETO (explicadas ao longo do arquivo):
--   • A autenticação usa o Supabase Auth (auth.users), não senhas nossas.
--   • Dados sensíveis (CNH, endereço) ficam em tabela separada e restrita.
--   • Toda tabela tem RLS ligada: sem política que permita, ninguém lê nada.
-- ============================================================================


-- ============================================================================
-- 1. CARGOS — as 12 funções oficiais da ficha
-- ============================================================================
create table if not exists public.cargos (
  nome              text primary key,
  ordem             int  not null,          -- hierarquia, para ordenar listagens
  e_diretoria       boolean not null default false,
  permissoes_padrao text[] not null default '{}'
);

comment on table public.cargos is
  'Funções oficiais do M.C., conforme a Ficha cadastral membros.';
comment on column public.cargos.permissoes_padrao is
  'Permissões que a função concede por padrão. Ajustes individuais ficam em perfis.permissoes_customizadas.';

insert into public.cargos (nome, ordem, e_diretoria, permissoes_padrao) values
  ('Presidente', 1, true, array[
     'ver_dashboard','ver_integrantes','editar_integrantes','excluir_integrantes',
     'ver_dados_sensiveis','ver_financeiro','editar_financeiro','ver_eventos','editar_eventos',
     'ver_comunicados','editar_comunicados','ver_documentos','editar_documentos',
     'ver_solicitacoes','analisar_solicitacoes','gerenciar_acessos']),

  ('Vice Presidente', 2, true, array[
     'ver_dashboard','ver_integrantes','editar_integrantes',
     'ver_dados_sensiveis','ver_financeiro','ver_eventos','editar_eventos',
     'ver_comunicados','editar_comunicados','ver_documentos','editar_documentos',
     'ver_solicitacoes','analisar_solicitacoes','gerenciar_acessos']),

  ('Diretor Geral', 3, true, array[
     'ver_dashboard','ver_integrantes','editar_integrantes',
     'ver_dados_sensiveis','ver_financeiro','ver_eventos','editar_eventos',
     'ver_comunicados','editar_comunicados','ver_documentos','editar_documentos',
     'ver_solicitacoes','analisar_solicitacoes']),

  ('Diretor Disciplina', 4, true, array[
     'ver_dashboard','ver_integrantes','ver_dados_sensiveis','ver_eventos',
     'ver_comunicados','editar_comunicados','ver_documentos',
     'ver_solicitacoes','analisar_solicitacoes']),

  ('Diretor Social', 5, true, array[
     'ver_dashboard','ver_integrantes','ver_eventos','editar_eventos',
     'ver_comunicados','editar_comunicados','ver_documentos']),

  ('Diretor de Eventos', 6, true, array[
     'ver_dashboard','ver_integrantes','ver_eventos','editar_eventos',
     'ver_comunicados','ver_documentos']),

  ('Tesoureiro', 7, true, array[
     'ver_dashboard','ver_integrantes','ver_financeiro','editar_financeiro',
     'ver_eventos','ver_comunicados','ver_documentos','editar_documentos']),

  ('Secretário', 8, true, array[
     'ver_dashboard','ver_integrantes','editar_integrantes','ver_dados_sensiveis',
     'ver_eventos','editar_eventos','ver_comunicados','editar_comunicados',
     'ver_documentos','editar_documentos','ver_solicitacoes','analisar_solicitacoes']),

  ('Conselheiro', 9, true, array[
     'ver_dashboard','ver_integrantes','ver_financeiro','ver_eventos',
     'ver_comunicados','ver_documentos','ver_solicitacoes']),

  ('Imprensa/Marketing', 10, true, array[
     'ver_dashboard','ver_integrantes','ver_eventos',
     'ver_comunicados','editar_comunicados','ver_documentos']),

  ('Membro com Brasão', 11, false, array[
     'ver_dashboard','ver_integrantes','ver_eventos','ver_comunicados','ver_documentos']),

  ('Próspero', 12, false, array[
     'ver_dashboard','ver_eventos','ver_comunicados'])
on conflict (nome) do nothing;


-- Catálogo de permissões (usado pela tela de Acessos do portal)
create table if not exists public.permissoes_catalogo (
  chave text primary key,
  label text not null,
  grupo text not null,
  ordem int  not null
);

insert into public.permissoes_catalogo (chave, label, grupo, ordem) values
  ('ver_dashboard',        'Ver o dashboard',                          'Geral',          1),
  ('ver_integrantes',      'Ver a lista de integrantes',               'Integrantes',    2),
  ('editar_integrantes',   'Cadastrar e editar integrantes',           'Integrantes',    3),
  ('excluir_integrantes',  'Excluir integrantes',                      'Integrantes',    4),
  ('ver_dados_sensiveis',  'Ver CNH e endereço dos integrantes',       'Integrantes',    5),
  ('ver_financeiro',       'Ver mensalidades e caixa',                 'Financeiro',     6),
  ('editar_financeiro',    'Lançar mensalidades e registrar pagamentos','Financeiro',    7),
  ('ver_eventos',          'Ver eventos e confirmar presença',         'Eventos',        8),
  ('editar_eventos',       'Criar, editar e excluir eventos',          'Eventos',        9),
  ('ver_comunicados',      'Ver comunicados',                          'Comunicados',   10),
  ('editar_comunicados',   'Publicar e excluir comunicados',           'Comunicados',   11),
  ('ver_documentos',       'Ver e baixar documentos',                  'Documentos',    12),
  ('editar_documentos',    'Enviar e excluir documentos',              'Documentos',    13),
  ('ver_solicitacoes',     'Ver solicitações de ingresso',             'Solicitações',  14),
  ('analisar_solicitacoes','Aprovar e recusar solicitações',           'Solicitações',  15),
  ('gerenciar_acessos',    'Gerenciar acessos e permissões',           'Administração', 16)
on conflict (chave) do nothing;


-- ============================================================================
-- 2. INTEGRANTES — espelha a ficha cadastral
-- ============================================================================
create table if not exists public.integrantes (
  id                bigint generated always as identity primary key,

  -- campos da ficha
  nome_completo     text not null,
  email             text,
  telefone          text,
  nome_no_colete    text,                       -- "Nome no colete" = apelido no M.C.
  cargo             text not null default 'Próspero' references public.cargos(nome)
                       on update cascade,
  padrinho_nome     text,                       -- como veio na ficha (texto livre)
  padrinho_id       bigint references public.integrantes(id) on delete set null,
  tipo_sanguineo    text,
  data_nascimento   date,
  entrada_mes_ano   text,                       -- ficha pede "mês e ano", não data completa
  veiculo_principal text check (veiculo_principal in ('Carro','Moto')),
  placa_veiculo     text,

  -- controle interno do portal
  status            text not null default 'Ativo' check (status in ('Ativo','Inativo')),
  foto_url          text,
  observacoes       text,
  criado_em         timestamptz not null default now(),
  atualizado_em     timestamptz not null default now()
);

comment on column public.integrantes.nome_no_colete is
  'Campo "Nome no colete" da ficha — é o apelido usado dentro do M.C.';
comment on column public.integrantes.entrada_mes_ano is
  'A ficha pede apenas mês e ano de entrada, por isso é texto (ex.: "03/2019") e não date.';
comment on column public.integrantes.padrinho_id is
  'Preenchido quando o padrinho também é integrante cadastrado. padrinho_nome guarda o texto original da ficha.';

create index if not exists idx_integrantes_cargo  on public.integrantes(cargo);
create index if not exists idx_integrantes_status on public.integrantes(status);


-- ----------------------------------------------------------------------------
-- 2b. DADOS SENSÍVEIS em tabela separada
-- ----------------------------------------------------------------------------
-- Por que separar: o RLS do Postgres protege LINHAS, não COLUNAS. Se a CNH e o
-- endereço ficassem na mesma tabela, qualquer integrante que pudesse ver a lista
-- veria também esses dados. Numa tabela à parte, o acesso é controlado de forma
-- independente e só quem tem 'ver_dados_sensiveis' enxerga.
-- ----------------------------------------------------------------------------
create table if not exists public.integrantes_dados_sensiveis (
  integrante_id       bigint primary key references public.integrantes(id) on delete cascade,
  endereco            text,
  habilitacao_numero  text,
  atualizado_em       timestamptz not null default now()
);

comment on table public.integrantes_dados_sensiveis is
  'Endereço e nº da CNH. Separado de integrantes porque RLS filtra linhas, não colunas.';


-- ============================================================================
-- 3. PERFIS — liga o login (Supabase Auth) ao integrante
-- ============================================================================
-- Não guardamos senha: quem cuida disso é o Supabase Auth (auth.users), com
-- hash forte, recuperação por e-mail e proteção contra ataques de força bruta.
-- ============================================================================
create table if not exists public.perfis (
  user_id                 uuid primary key references auth.users(id) on delete cascade,
  integrante_id           bigint unique references public.integrantes(id) on delete cascade,
  cargo                   text not null default 'Próspero' references public.cargos(nome)
                             on update cascade,
  ativo                   boolean not null default true,
  permissoes_customizadas jsonb not null default '{}'::jsonb,
  criado_em               timestamptz not null default now()
);

comment on column public.perfis.permissoes_customizadas is
  'Ajustes individuais sobre o padrão do cargo: {"ver_financeiro": true, "editar_eventos": false}';


-- Mantém o cargo do perfil e do integrante sempre iguais.
-- Sem isso, promover alguém na lista de integrantes não mudaria o acesso dele.
create or replace function public.sincronizar_cargo()
returns trigger language plpgsql as $$
begin
  if tg_table_name = 'integrantes' then
    update public.perfis set cargo = new.cargo
      where integrante_id = new.id and cargo is distinct from new.cargo;
  else
    update public.integrantes set cargo = new.cargo
      where id = new.integrante_id and cargo is distinct from new.cargo;
  end if;
  return new;
end $$;

drop trigger if exists trg_sync_cargo_integrante on public.integrantes;
create trigger trg_sync_cargo_integrante
  after update of cargo on public.integrantes
  for each row execute function public.sincronizar_cargo();

drop trigger if exists trg_sync_cargo_perfil on public.perfis;
create trigger trg_sync_cargo_perfil
  after update of cargo on public.perfis
  for each row execute function public.sincronizar_cargo();


-- ============================================================================
-- 4. FUNÇÕES DE PERMISSÃO
-- ============================================================================
-- security definer: rodam com privilégio do dono, para poderem consultar perfis
-- sem cair na própria RLS (o que causaria recursão infinita nas políticas).
-- ============================================================================
create or replace function public.permissoes_efetivas(p_cargo text, p_custom jsonb)
returns text[] language sql stable as $$
  select coalesce(
    array(
      select distinct chave from (
        -- permissões que vêm do cargo, menos as bloqueadas individualmente
        select unnest(c.permissoes_padrao) as chave
          from public.cargos c where c.nome = p_cargo
        union
        -- permissões liberadas individualmente
        select k from jsonb_each(coalesce(p_custom,'{}'::jsonb)) as t(k,v)
          where v = 'true'::jsonb
      ) todas
      where chave not in (
        select k from jsonb_each(coalesce(p_custom,'{}'::jsonb)) as t(k,v)
          where v = 'false'::jsonb
      )
    ), '{}'::text[]);
$$;

create or replace function public.tem_permissao(p_chave text)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.perfis p
     where p.user_id = auth.uid()
       and p.ativo
       and p_chave = any(public.permissoes_efetivas(p.cargo, p.permissoes_customizadas))
  );
$$;

create or replace function public.meu_integrante_id()
returns bigint language sql stable security definer set search_path = public as $$
  select integrante_id from public.perfis where user_id = auth.uid();
$$;

create or replace function public.minhas_permissoes()
returns text[] language sql stable security definer set search_path = public as $$
  select public.permissoes_efetivas(p.cargo, p.permissoes_customizadas)
    from public.perfis p where p.user_id = auth.uid() and p.ativo;
$$;


-- ============================================================================
-- 5. FINANCEIRO
-- ============================================================================
create table if not exists public.mensalidades (
  id              bigint generated always as identity primary key,
  integrante_id   bigint not null references public.integrantes(id) on delete cascade,
  referencia      text   not null,                    -- 'AAAA-MM'
  vencimento      date   not null,
  valor           numeric(10,2) not null default 40.00,
  pago            boolean not null default false,
  data_pagamento  date,
  forma_pagamento text,
  criado_em       timestamptz not null default now(),
  unique (integrante_id, referencia)                  -- evita cobrar 2x o mesmo mês
);

create table if not exists public.caixa (
  id            bigint generated always as identity primary key,
  tipo          text not null check (tipo in ('Entrada','Saída')),
  descricao     text not null,
  valor         numeric(10,2) not null check (valor >= 0),
  data          date not null default current_date,
  mensalidade_id bigint references public.mensalidades(id) on delete set null,
  registrado_por bigint references public.integrantes(id) on delete set null,
  criado_em     timestamptz not null default now()
);

-- Todo pagamento registrado vira entrada no caixa automaticamente
create or replace function public.lancar_mensalidade_no_caixa()
returns trigger language plpgsql as $$
declare v_nome text;
begin
  if new.pago and not coalesce(old.pago,false) then
    select nome_completo into v_nome from public.integrantes where id = new.integrante_id;
    insert into public.caixa (tipo, descricao, valor, data, mensalidade_id)
    values ('Entrada',
            'Mensalidade ' || new.referencia || ' - ' || coalesce(v_nome,'#'||new.integrante_id),
            new.valor,
            coalesce(new.data_pagamento, current_date),
            new.id);
  end if;
  return new;
end $$;

drop trigger if exists trg_mensalidade_caixa on public.mensalidades;
create trigger trg_mensalidade_caixa
  after update of pago on public.mensalidades
  for each row execute function public.lancar_mensalidade_no_caixa();


-- ============================================================================
-- 6. EVENTOS E PRESENÇAS
-- ============================================================================
create table if not exists public.eventos (
  id          bigint generated always as identity primary key,
  nome        text not null,
  data        date not null,
  local       text,
  descricao   text,
  tipo        text not null default 'Encontro'
                check (tipo in ('Passeio','Encontro','Churrasco','Aniversário','Reunião','Outro')),
  status      text not null default 'Planejado'
                check (status in ('Planejado','Confirmado','Realizado','Cancelado')),
  criador_id  bigint references public.integrantes(id) on delete set null,
  criado_em   timestamptz not null default now()
);

create table if not exists public.presencas (
  id            bigint generated always as identity primary key,
  evento_id     bigint not null references public.eventos(id) on delete cascade,
  integrante_id bigint not null references public.integrantes(id) on delete cascade,
  confirmacao   text not null default 'Pendente'
                  check (confirmacao in ('Pendente','Confirmado','Recusado')),
  atualizado_em timestamptz not null default now(),
  unique (evento_id, integrante_id)
);


-- ============================================================================
-- 7. COMUNICADOS E DOCUMENTOS
-- ============================================================================
create table if not exists public.comunicados (
  id        bigint generated always as identity primary key,
  titulo    text not null,
  mensagem  text not null,
  fixado    boolean not null default false,
  autor_id  bigint references public.integrantes(id) on delete set null,
  criado_em timestamptz not null default now()
);

create table if not exists public.documentos (
  id            bigint generated always as identity primary key,
  titulo        text not null,
  categoria     text not null default 'Outro'
                  check (categoria in ('Ata','Regimento','Contrato','Financeiro','Outro')),
  arquivo_nome  text not null,
  storage_path  text not null,          -- caminho no Supabase Storage
  tamanho_kb    int  not null default 0,
  enviado_por   bigint references public.integrantes(id) on delete set null,
  criado_em     timestamptz not null default now()
);


-- ============================================================================
-- 8. SOLICITAÇÕES DE INGRESSO — mesmos campos da ficha
-- ============================================================================
create table if not exists public.solicitacoes_cadastro (
  id                   bigint generated always as identity primary key,
  nome_completo        text not null,
  email                text,
  telefone             text not null,
  endereco             text,
  nome_no_colete       text,
  padrinho_nome        text,
  tipo_sanguineo       text,
  data_nascimento      date,
  veiculo_principal    text check (veiculo_principal in ('Carro','Moto')),
  placa_veiculo        text,
  habilitacao_numero   text,
  mensagem             text,
  status               text not null default 'Pendente'
                         check (status in ('Pendente','Aprovada','Recusada')),
  analisado_por        bigint references public.integrantes(id) on delete set null,
  data_analise         timestamptz,
  integrante_criado_id bigint references public.integrantes(id) on delete set null,
  criado_em            timestamptz not null default now()
);


-- ============================================================================
-- 9. ROW LEVEL SECURITY
-- ============================================================================
-- Com RLS ligada e sem política correspondente, a operação é NEGADA.
-- É o comportamento que queremos: nada vaza por esquecimento.
-- ============================================================================
alter table public.integrantes                 enable row level security;
alter table public.integrantes_dados_sensiveis enable row level security;
alter table public.perfis                      enable row level security;
alter table public.mensalidades                enable row level security;
alter table public.caixa                       enable row level security;
alter table public.eventos                     enable row level security;
alter table public.presencas                   enable row level security;
alter table public.comunicados                 enable row level security;
alter table public.documentos                  enable row level security;
alter table public.solicitacoes_cadastro       enable row level security;
alter table public.cargos                      enable row level security;
alter table public.permissoes_catalogo         enable row level security;

-- Tabelas de apoio: qualquer pessoa autenticada pode ler
drop policy if exists cargos_leitura on public.cargos;
create policy cargos_leitura on public.cargos
  for select to authenticated using (true);

drop policy if exists catalogo_leitura on public.permissoes_catalogo;
create policy catalogo_leitura on public.permissoes_catalogo
  for select to authenticated using (true);

-- ---- Integrantes ----
drop policy if exists integrantes_ler on public.integrantes;
create policy integrantes_ler on public.integrantes
  for select to authenticated
  using (public.tem_permissao('ver_integrantes') or id = public.meu_integrante_id());

drop policy if exists integrantes_inserir on public.integrantes;
create policy integrantes_inserir on public.integrantes
  for insert to authenticated with check (public.tem_permissao('editar_integrantes'));

drop policy if exists integrantes_atualizar on public.integrantes;
create policy integrantes_atualizar on public.integrantes
  for update to authenticated using (public.tem_permissao('editar_integrantes'));

drop policy if exists integrantes_excluir on public.integrantes;
create policy integrantes_excluir on public.integrantes
  for delete to authenticated using (public.tem_permissao('excluir_integrantes'));

-- ---- Dados sensíveis: só a diretoria autorizada, ou o próprio dono ----
drop policy if exists sensiveis_ler on public.integrantes_dados_sensiveis;
create policy sensiveis_ler on public.integrantes_dados_sensiveis
  for select to authenticated
  using (public.tem_permissao('ver_dados_sensiveis') or integrante_id = public.meu_integrante_id());

-- ATENÇÃO: as políticas de escrita são declaradas por operação (insert/update/
-- delete) e NUNCA com "for all". No Postgres, "for all" também vale para SELECT,
-- e como as políticas se SOMAM, uma permissão de escrita acabaria liberando a
-- leitura — furando um bloqueio individual de 'ver_*'.
drop policy if exists sensiveis_gravar on public.integrantes_dados_sensiveis;
drop policy if exists sensiveis_inserir on public.integrantes_dados_sensiveis;
create policy sensiveis_inserir on public.integrantes_dados_sensiveis
  for insert to authenticated with check (public.tem_permissao('editar_integrantes'));
drop policy if exists sensiveis_atualizar on public.integrantes_dados_sensiveis;
create policy sensiveis_atualizar on public.integrantes_dados_sensiveis
  for update to authenticated
  using (public.tem_permissao('editar_integrantes'))
  with check (public.tem_permissao('editar_integrantes'));
drop policy if exists sensiveis_excluir on public.integrantes_dados_sensiveis;
create policy sensiveis_excluir on public.integrantes_dados_sensiveis
  for delete to authenticated using (public.tem_permissao('editar_integrantes'));

-- ---- Perfis ----
drop policy if exists perfis_ler on public.perfis;
create policy perfis_ler on public.perfis
  for select to authenticated
  using (user_id = auth.uid() or public.tem_permissao('gerenciar_acessos'));

drop policy if exists perfis_gravar on public.perfis;
drop policy if exists perfis_inserir on public.perfis;
create policy perfis_inserir on public.perfis
  for insert to authenticated with check (public.tem_permissao('gerenciar_acessos'));
drop policy if exists perfis_atualizar on public.perfis;
create policy perfis_atualizar on public.perfis
  for update to authenticated
  using (public.tem_permissao('gerenciar_acessos'))
  with check (public.tem_permissao('gerenciar_acessos'));
drop policy if exists perfis_excluir on public.perfis;
create policy perfis_excluir on public.perfis
  for delete to authenticated using (public.tem_permissao('gerenciar_acessos'));

-- ---- Financeiro ----
drop policy if exists mensalidades_ler on public.mensalidades;
create policy mensalidades_ler on public.mensalidades
  for select to authenticated
  using (public.tem_permissao('ver_financeiro') or integrante_id = public.meu_integrante_id());

drop policy if exists mensalidades_gravar on public.mensalidades;
drop policy if exists mensalidades_inserir on public.mensalidades;
create policy mensalidades_inserir on public.mensalidades
  for insert to authenticated with check (public.tem_permissao('editar_financeiro'));
drop policy if exists mensalidades_atualizar on public.mensalidades;
create policy mensalidades_atualizar on public.mensalidades
  for update to authenticated
  using (public.tem_permissao('editar_financeiro'))
  with check (public.tem_permissao('editar_financeiro'));
drop policy if exists mensalidades_excluir on public.mensalidades;
create policy mensalidades_excluir on public.mensalidades
  for delete to authenticated using (public.tem_permissao('editar_financeiro'));

drop policy if exists caixa_ler on public.caixa;
create policy caixa_ler on public.caixa
  for select to authenticated using (public.tem_permissao('ver_financeiro'));

drop policy if exists caixa_gravar on public.caixa;
drop policy if exists caixa_inserir on public.caixa;
create policy caixa_inserir on public.caixa
  for insert to authenticated with check (public.tem_permissao('editar_financeiro'));
drop policy if exists caixa_atualizar on public.caixa;
create policy caixa_atualizar on public.caixa
  for update to authenticated
  using (public.tem_permissao('editar_financeiro'))
  with check (public.tem_permissao('editar_financeiro'));
drop policy if exists caixa_excluir on public.caixa;
create policy caixa_excluir on public.caixa
  for delete to authenticated using (public.tem_permissao('editar_financeiro'));

-- ---- Eventos ----
drop policy if exists eventos_ler on public.eventos;
create policy eventos_ler on public.eventos
  for select to authenticated using (public.tem_permissao('ver_eventos'));

drop policy if exists eventos_gravar on public.eventos;
drop policy if exists eventos_inserir on public.eventos;
create policy eventos_inserir on public.eventos
  for insert to authenticated with check (public.tem_permissao('editar_eventos'));
drop policy if exists eventos_atualizar on public.eventos;
create policy eventos_atualizar on public.eventos
  for update to authenticated
  using (public.tem_permissao('editar_eventos'))
  with check (public.tem_permissao('editar_eventos'));
drop policy if exists eventos_excluir on public.eventos;
create policy eventos_excluir on public.eventos
  for delete to authenticated using (public.tem_permissao('editar_eventos'));

-- Presença: cada um responde pela sua; quem organiza pode ajustar qualquer uma
drop policy if exists presencas_ler on public.presencas;
create policy presencas_ler on public.presencas
  for select to authenticated using (public.tem_permissao('ver_eventos'));

drop policy if exists presencas_propria on public.presencas;
drop policy if exists presencas_inserir on public.presencas;
create policy presencas_inserir on public.presencas
  for insert to authenticated
  with check (integrante_id = public.meu_integrante_id() or public.tem_permissao('editar_eventos'));
drop policy if exists presencas_atualizar on public.presencas;
create policy presencas_atualizar on public.presencas
  for update to authenticated
  using (integrante_id = public.meu_integrante_id() or public.tem_permissao('editar_eventos'))
  with check (integrante_id = public.meu_integrante_id() or public.tem_permissao('editar_eventos'));
drop policy if exists presencas_excluir on public.presencas;
create policy presencas_excluir on public.presencas
  for delete to authenticated
  using (integrante_id = public.meu_integrante_id() or public.tem_permissao('editar_eventos'));

-- ---- Comunicados ----
drop policy if exists comunicados_ler on public.comunicados;
create policy comunicados_ler on public.comunicados
  for select to authenticated using (public.tem_permissao('ver_comunicados'));

drop policy if exists comunicados_gravar on public.comunicados;
drop policy if exists comunicados_inserir on public.comunicados;
create policy comunicados_inserir on public.comunicados
  for insert to authenticated with check (public.tem_permissao('editar_comunicados'));
drop policy if exists comunicados_atualizar on public.comunicados;
create policy comunicados_atualizar on public.comunicados
  for update to authenticated
  using (public.tem_permissao('editar_comunicados'))
  with check (public.tem_permissao('editar_comunicados'));
drop policy if exists comunicados_excluir on public.comunicados;
create policy comunicados_excluir on public.comunicados
  for delete to authenticated using (public.tem_permissao('editar_comunicados'));

-- ---- Documentos ----
drop policy if exists documentos_ler on public.documentos;
create policy documentos_ler on public.documentos
  for select to authenticated using (public.tem_permissao('ver_documentos'));

drop policy if exists documentos_gravar on public.documentos;
drop policy if exists documentos_inserir on public.documentos;
create policy documentos_inserir on public.documentos
  for insert to authenticated with check (public.tem_permissao('editar_documentos'));
drop policy if exists documentos_atualizar on public.documentos;
create policy documentos_atualizar on public.documentos
  for update to authenticated
  using (public.tem_permissao('editar_documentos'))
  with check (public.tem_permissao('editar_documentos'));
drop policy if exists documentos_excluir on public.documentos;
create policy documentos_excluir on public.documentos
  for delete to authenticated using (public.tem_permissao('editar_documentos'));

-- ---- Solicitações: qualquer visitante pode ENVIAR, só a diretoria LÊ ----
drop policy if exists solicitacoes_enviar on public.solicitacoes_cadastro;
create policy solicitacoes_enviar on public.solicitacoes_cadastro
  for insert to anon, authenticated with check (true);

drop policy if exists solicitacoes_ler on public.solicitacoes_cadastro;
create policy solicitacoes_ler on public.solicitacoes_cadastro
  for select to authenticated using (public.tem_permissao('ver_solicitacoes'));

drop policy if exists solicitacoes_analisar on public.solicitacoes_cadastro;
create policy solicitacoes_analisar on public.solicitacoes_cadastro
  for update to authenticated
  using (public.tem_permissao('analisar_solicitacoes'))
  with check (public.tem_permissao('analisar_solicitacoes'));


-- ============================================================================
-- 10. VISÕES DE APOIO
-- ============================================================================
-- security_invoker = true faz a view respeitar a RLS de quem consulta.
-- Sem isso, a view rodaria com o privilégio do dono e furaria as políticas.
-- ============================================================================
create or replace view public.vw_aniversariantes_mes
with (security_invoker = true) as
  select id, nome_completo, nome_no_colete, data_nascimento,
         extract(day from data_nascimento)::int as dia
    from public.integrantes
   where status = 'Ativo'
     and data_nascimento is not null
     and extract(month from data_nascimento) = extract(month from current_date)
   order by dia;

create or replace view public.vw_dashboard
with (security_invoker = true) as
  select
    (select count(*) from public.integrantes where status = 'Ativo')            as total_integrantes,
    (select coalesce(round(
        100.0 * count(*) filter (where pago) / nullif(count(*),0), 1), 0)
       from public.mensalidades
      where referencia = to_char(current_date,'YYYY-MM'))                       as percentual_pagas,
    (select coalesce(sum(case when tipo = 'Entrada' then valor else -valor end), 0)
       from public.caixa)                                                       as saldo_caixa,
    (select nome from public.eventos
      where data >= current_date order by data limit 1)                         as proximo_evento_nome,
    (select data from public.eventos
      where data >= current_date order by data limit 1)                         as proximo_evento_data;


-- ============================================================================
-- 11. ATUALIZAÇÃO AUTOMÁTICA DE atualizado_em
-- ============================================================================
create or replace function public.marcar_atualizacao()
returns trigger language plpgsql as $$
begin
  new.atualizado_em := now();
  return new;
end $$;

drop trigger if exists trg_integrantes_atualizado on public.integrantes;
create trigger trg_integrantes_atualizado before update on public.integrantes
  for each row execute function public.marcar_atualizacao();

drop trigger if exists trg_sensiveis_atualizado on public.integrantes_dados_sensiveis;
create trigger trg_sensiveis_atualizado before update on public.integrantes_dados_sensiveis
  for each row execute function public.marcar_atualizacao();

drop trigger if exists trg_presencas_atualizado on public.presencas;
create trigger trg_presencas_atualizado before update on public.presencas
  for each row execute function public.marcar_atualizacao();


-- ============================================================================
-- FIM. Próximo passo: 02-importar-respostas.sql
-- ============================================================================

-- ============================================================================
-- 12. ENDURECIMENTO DE SEGURANÇA (apontado pelo verificador do Supabase)
-- ============================================================================
-- Fixa o search_path: sem isso, alguém poderia criar um schema com objetos de
-- mesmo nome e fazer a função usar os objetos errados.
alter function public.permissoes_efetivas(text, jsonb) set search_path = public;
alter function public.sincronizar_cargo()              set search_path = public;
alter function public.lancar_mensalidade_no_caixa()    set search_path = public;
alter function public.marcar_atualizacao()             set search_path = public;

-- Toda função nasce com EXECUTE liberado para PUBLIC. Revogamos e devolvemos
-- apenas a quem precisa: as políticas de segurança chamam estas funções em nome
-- do usuário logado, então 'authenticated' precisa mantê-las.
revoke execute on function public.tem_permissao(text)              from public, anon;
revoke execute on function public.meu_integrante_id()              from public, anon;
revoke execute on function public.minhas_permissoes()              from public, anon;
revoke execute on function public.permissoes_efetivas(text, jsonb) from public, anon;

grant execute on function public.tem_permissao(text)              to authenticated;
grant execute on function public.meu_integrante_id()              to authenticated;
grant execute on function public.minhas_permissoes()              to authenticated;
grant execute on function public.permissoes_efetivas(text, jsonb) to authenticated;

-- ============================================================================
-- 13. IMAGEM NOS COMUNICADOS
-- ============================================================================
-- Guardamos o CAMINHO no Storage, não a URL completa: assim o bucket pode mudar
-- de nome ou visibilidade sem invalidar os registros já publicados.
alter table public.comunicados
  add column if not exists imagem_path text;

comment on column public.comunicados.imagem_path is
  'Caminho da imagem no bucket comunicados do Storage. Nulo quando o aviso não tem imagem.';

-- Bucket público: a imagem de um aviso é para todos os integrantes verem, e
-- arquivo público é servido pelo CDN (bem mais rápido no celular).
-- Nada sensível aqui — atas e contratos ficam em bucket privado.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('comunicados', 'comunicados', true, 5242880,
        array['image/jpeg','image/png','image/webp','image/gif'])
on conflict (id) do update
  set public = true,
      file_size_limit = 5242880,
      allowed_mime_types = array['image/jpeg','image/png','image/webp','image/gif'];

drop policy if exists comunicados_img_ler on storage.objects;
create policy comunicados_img_ler on storage.objects
  for select to public using (bucket_id = 'comunicados');

drop policy if exists comunicados_img_enviar on storage.objects;
create policy comunicados_img_enviar on storage.objects
  for insert to authenticated
  with check (bucket_id = 'comunicados' and public.tem_permissao('editar_comunicados'));

drop policy if exists comunicados_img_atualizar on storage.objects;
create policy comunicados_img_atualizar on storage.objects
  for update to authenticated
  using (bucket_id = 'comunicados' and public.tem_permissao('editar_comunicados'))
  with check (bucket_id = 'comunicados' and public.tem_permissao('editar_comunicados'));

drop policy if exists comunicados_img_excluir on storage.objects;
create policy comunicados_img_excluir on storage.objects
  for delete to authenticated
  using (bucket_id = 'comunicados' and public.tem_permissao('editar_comunicados'));

-- ============================================================================
-- 14. IMAGEM NOS EVENTOS
-- ============================================================================
-- Bucket separado do de comunicados de propósito: assim quem pode publicar
-- evento mexe só nas imagens de evento, e vice-versa.
alter table public.eventos
  add column if not exists imagem_path text;

comment on column public.eventos.imagem_path is
  'Caminho da imagem no bucket eventos do Storage. Nulo quando o evento não tem cartaz/foto.';

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('eventos', 'eventos', true, 5242880,
        array['image/jpeg','image/png','image/webp','image/gif'])
on conflict (id) do update
  set public = true,
      file_size_limit = 5242880,
      allowed_mime_types = array['image/jpeg','image/png','image/webp','image/gif'];

drop policy if exists eventos_img_ler on storage.objects;
create policy eventos_img_ler on storage.objects
  for select to public using (bucket_id = 'eventos');

drop policy if exists eventos_img_enviar on storage.objects;
create policy eventos_img_enviar on storage.objects
  for insert to authenticated
  with check (bucket_id = 'eventos' and public.tem_permissao('editar_eventos'));

drop policy if exists eventos_img_atualizar on storage.objects;
create policy eventos_img_atualizar on storage.objects
  for update to authenticated
  using (bucket_id = 'eventos' and public.tem_permissao('editar_eventos'))
  with check (bucket_id = 'eventos' and public.tem_permissao('editar_eventos'));

drop policy if exists eventos_img_excluir on storage.objects;
create policy eventos_img_excluir on storage.objects
  for delete to authenticated
  using (bucket_id = 'eventos' and public.tem_permissao('editar_eventos'));
