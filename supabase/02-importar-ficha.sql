-- ============================================================================
-- PORTAL IMACULADOS M.C. — Importar as respostas da Ficha cadastral
-- ============================================================================
-- Rode este arquivo DEPOIS do 01-schema.sql.
--
-- PASSO 1 — Exportar as respostas do Formulário
--   No Google Forms → aba "Respostas" → ícone verde do Sheets → abre a planilha
--   Na planilha → Arquivo → Fazer download → Valores separados por vírgula (.csv)
--
-- PASSO 2 — Subir o CSV para o Supabase
--   Supabase → Table Editor → tabela "importacao_ficha" (criada abaixo)
--   → botão "Insert" → "Import data from CSV"
--
-- PASSO 3 — Rodar a parte 2 deste arquivo, que move os dados para o lugar certo
-- ============================================================================


-- ============================================================================
-- PARTE 1 — Tabela de recepção (tudo como texto, para nada ser rejeitado)
-- ============================================================================
-- Importar direto para 'integrantes' daria erro em qualquer data mal formatada
-- ou cargo escrito diferente. Recebendo tudo como texto primeiro, conseguimos
-- conferir e corrigir antes de gravar de verdade.
-- ============================================================================
drop table if exists public.importacao_ficha;
create table public.importacao_ficha (
  carimbo_data_hora  text,
  email_registrado   text,
  nome_completo      text,
  email              text,
  endereco           text,
  telefone           text,
  nome_no_colete     text,
  funcao             text,
  padrinho           text,
  tipo_sanguineo     text,
  data_nascimento    text,
  entrada_mes_ano    text,
  habilitacao        text,
  veiculo_principal  text,
  placa_veiculo      text
);

comment on table public.importacao_ficha is
  'Área de recepção do CSV do Google Forms. Pode ser apagada depois da importação.';

alter table public.importacao_ficha enable row level security;
drop policy if exists importacao_admin on public.importacao_ficha;
create policy importacao_admin on public.importacao_ficha
  for select to authenticated using (public.tem_permissao('gerenciar_acessos'));


-- ============================================================================
-- PARTE 2 — Conferência ANTES de importar (rode e leia o resultado)
-- ============================================================================
-- Descomente e execute para ver o que seria importado e o que daria problema:

-- -- 2a. Quantas linhas chegaram?
-- select count(*) as linhas_no_csv from public.importacao_ficha;

-- -- 2b. Funções que NÃO batem com os cargos oficiais (precisam ser corrigidas)
-- select distinct i.funcao, count(*) as quantas
--   from public.importacao_ficha i
--   left join public.cargos c on c.nome = trim(i.funcao)
--  where c.nome is null
--  group by i.funcao;

-- -- 2c. Datas de nascimento que o banco não conseguiria interpretar
-- select nome_completo, data_nascimento
--   from public.importacao_ficha
--  where data_nascimento is not null and trim(data_nascimento) <> ''
--    and public.tentar_data(data_nascimento) is null;

-- -- 2d. Nomes repetidos (possíveis duplicatas)
-- select nome_completo, count(*) from public.importacao_ficha
--  group by nome_completo having count(*) > 1;


-- Converte data em vários formatos sem quebrar a importação.
-- O Google Forms exporta em MM/DD/AAAA, mas planilhas em português costumam
-- gravar DD/MM/AAAA — por isso testamos os dois.
create or replace function public.tentar_data(p_texto text)
returns date language plpgsql immutable as $$
declare v date;
begin
  if p_texto is null or trim(p_texto) = '' then return null; end if;
  begin v := to_date(trim(p_texto), 'MM/DD/YYYY'); return v; exception when others then end;
  begin v := to_date(trim(p_texto), 'DD/MM/YYYY'); return v; exception when others then end;
  begin v := to_date(trim(p_texto), 'YYYY-MM-DD'); return v; exception when others then end;
  return null;
end $$;

-- Remove acentos sem depender da extensão unaccent (nem sempre habilitada).
create or replace function public.unaccent_simples(p_texto text)
returns text language sql immutable as $$
  select translate(coalesce(p_texto,''),
                   'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                   'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC');
$$;

-- Normaliza o nome da função para os cargos oficiais.
-- Cobre variações de digitação que aparecem em formulários preenchidos à mão.
create or replace function public.normalizar_cargo(p_texto text)
returns text language sql immutable as $$
  select case
    when p_texto is null or trim(p_texto) = '' then 'Próspero'
    when trim(p_texto) in (select nome from public.cargos) then trim(p_texto)
    when lower(unaccent_simples(p_texto)) like '%vice%'            then 'Vice Presidente'
    when lower(unaccent_simples(p_texto)) like '%presidente%'      then 'Presidente'
    when lower(unaccent_simples(p_texto)) like '%geral%'           then 'Diretor Geral'
    when lower(unaccent_simples(p_texto)) like '%disciplina%'      then 'Diretor Disciplina'
    when lower(unaccent_simples(p_texto)) like '%social%'          then 'Diretor Social'
    when lower(unaccent_simples(p_texto)) like '%evento%'          then 'Diretor de Eventos'
    when lower(unaccent_simples(p_texto)) like '%tesoureir%'       then 'Tesoureiro'
    when lower(unaccent_simples(p_texto)) like '%secretari%'       then 'Secretário'
    when lower(unaccent_simples(p_texto)) like '%conselheir%'      then 'Conselheiro'
    when lower(unaccent_simples(p_texto)) like '%imprensa%'
      or lower(unaccent_simples(p_texto)) like '%marketing%'       then 'Imprensa/Marketing'
    when lower(unaccent_simples(p_texto)) like '%brasao%'          then 'Membro com Brasão'
    when lower(unaccent_simples(p_texto)) like '%prospero%'        then 'Próspero'
    else 'Próspero'
  end;
$$;


-- ============================================================================
-- PARTE 3 — Importar de verdade
-- ============================================================================
-- Só rode depois de conferir a PARTE 2. É seguro rodar mais de uma vez:
-- integrantes já existentes (mesmo nome) são atualizados, não duplicados.
-- ============================================================================
do $$
declare r record; v_id bigint;
begin
  for r in select * from public.importacao_ficha where coalesce(trim(nome_completo),'') <> '' loop

    select id into v_id from public.integrantes
     where lower(trim(nome_completo)) = lower(trim(r.nome_completo)) limit 1;

    if v_id is null then
      insert into public.integrantes (
        nome_completo, email, telefone, nome_no_colete, cargo, padrinho_nome,
        tipo_sanguineo, data_nascimento, entrada_mes_ano, veiculo_principal, placa_veiculo)
      values (
        trim(r.nome_completo),
        nullif(trim(coalesce(r.email, r.email_registrado)),''),
        nullif(trim(r.telefone),''),
        nullif(trim(r.nome_no_colete),''),
        public.normalizar_cargo(r.funcao),
        nullif(trim(r.padrinho),''),
        nullif(trim(r.tipo_sanguineo),''),
        public.tentar_data(r.data_nascimento),
        nullif(trim(r.entrada_mes_ano),''),
        case when lower(public.unaccent_simples(r.veiculo_principal)) like '%moto%' then 'Moto'
             when lower(public.unaccent_simples(r.veiculo_principal)) like '%carro%' then 'Carro'
             else null end,
        nullif(upper(trim(r.placa_veiculo)),''))
      returning id into v_id;
    else
      update public.integrantes set
        email             = coalesce(nullif(trim(coalesce(r.email, r.email_registrado)),''), email),
        telefone          = coalesce(nullif(trim(r.telefone),''), telefone),
        nome_no_colete    = coalesce(nullif(trim(r.nome_no_colete),''), nome_no_colete),
        cargo             = public.normalizar_cargo(r.funcao),
        padrinho_nome     = coalesce(nullif(trim(r.padrinho),''), padrinho_nome),
        tipo_sanguineo    = coalesce(nullif(trim(r.tipo_sanguineo),''), tipo_sanguineo),
        data_nascimento   = coalesce(public.tentar_data(r.data_nascimento), data_nascimento),
        entrada_mes_ano   = coalesce(nullif(trim(r.entrada_mes_ano),''), entrada_mes_ano),
        placa_veiculo     = coalesce(nullif(upper(trim(r.placa_veiculo)),''), placa_veiculo)
      where id = v_id;
    end if;

    -- endereço e CNH vão para a tabela protegida
    if coalesce(trim(r.endereco),'') <> '' or coalesce(trim(r.habilitacao),'') <> '' then
      insert into public.integrantes_dados_sensiveis (integrante_id, endereco, habilitacao_numero)
      values (v_id, nullif(trim(r.endereco),''), nullif(trim(r.habilitacao),''))
      on conflict (integrante_id) do update set
        endereco           = coalesce(excluded.endereco, integrantes_dados_sensiveis.endereco),
        habilitacao_numero = coalesce(excluded.habilitacao_numero, integrantes_dados_sensiveis.habilitacao_numero),
        atualizado_em      = now();
    end if;

  end loop;
end $$;


-- ============================================================================
-- PARTE 4 — Ligar cada padrinho ao integrante correspondente
-- ============================================================================
-- A ficha traz o padrinho como texto. Aqui tentamos casar com quem já está
-- cadastrado, seja pelo nome completo, seja pelo nome no colete.
-- ============================================================================
update public.integrantes i
   set padrinho_id = p.id
  from public.integrantes p
 where i.padrinho_id is null
   and coalesce(trim(i.padrinho_nome),'') <> ''
   and p.id <> i.id
   and (
     lower(public.unaccent_simples(trim(i.padrinho_nome))) = lower(public.unaccent_simples(p.nome_completo))
     or lower(public.unaccent_simples(trim(i.padrinho_nome))) = lower(public.unaccent_simples(coalesce(p.nome_no_colete,'#')))
   );


-- ============================================================================
-- PARTE 5 — Conferir o resultado
-- ============================================================================
-- select cargo, count(*) from public.integrantes group by cargo order by 2 desc;
-- select count(*) as com_dados_sensiveis from public.integrantes_dados_sensiveis;
-- select count(*) as padrinhos_ligados from public.integrantes where padrinho_id is not null;
-- select nome_completo, nome_no_colete, cargo, data_nascimento from public.integrantes order by nome_completo;

-- Depois de conferir tudo, você pode limpar a área de recepção:
-- drop table public.importacao_ficha;

-- ============================================================================
-- ENDURECIMENTO DE SEGURANÇA
-- ============================================================================
alter function public.tentar_data(text)      set search_path = public;
alter function public.unaccent_simples(text) set search_path = public;
alter function public.normalizar_cargo(text) set search_path = public;
