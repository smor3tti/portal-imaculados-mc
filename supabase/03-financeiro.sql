-- ============================================================================
-- PORTAL IMACULADOS M.C. — Financeiro: afastamento, mensalidades e caixa
-- ============================================================================
-- Rode depois do 01-schema.sql. Já aplicado no projeto do Supabase.
--
-- REGRAS DEFINIDAS PELO CLUBE:
--   • Mensalidade R$ 40,00, vencimento dia 10, sem multa nem juros
--   • Afastado não paga; ao afastar, as cobranças em aberto são canceladas
--   • Na volta, o período afastado é perdoado (sem dívida acumulada)
--   • Qualquer um da diretoria pode afastar; só Tesoureiro e Presidente dão baixa
-- ============================================================================

-- ---- Afastamento: situação do integrante, não exceção lançada mês a mês ----
alter table public.integrantes drop constraint if exists integrantes_status_check;
alter table public.integrantes
  add constraint integrantes_status_check
  check (status in ('Ativo','Afastado','Inativo'));

alter table public.integrantes
  add column if not exists afastamento_desde  date,
  add column if not exists afastamento_motivo text,
  add column if not exists afastado_por       bigint references public.integrantes(id) on delete set null;

-- Cancelada continua na base, marcada. Apagar a linha esconderia o histórico.
alter table public.mensalidades
  add column if not exists cancelada           boolean not null default false,
  add column if not exists motivo_cancelamento text;

create index if not exists idx_mensalidades_abertas
  on public.mensalidades (referencia) where not pago and not cancelada;

alter table public.caixa
  add column if not exists categoria  text,
  add column if not exists automatico boolean not null default false;

create or replace function public.tratar_afastamento()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.status = 'Afastado' and coalesce(old.status,'') <> 'Afastado' then
    new.afastamento_desde := coalesce(new.afastamento_desde, current_date);
    update public.mensalidades
       set cancelada = true,
           motivo_cancelamento = 'Cancelada por afastamento do integrante'
     where integrante_id = new.id and not pago and not cancelada;
  elsif new.status <> 'Afastado' and coalesce(old.status,'') = 'Afastado' then
    new.afastamento_desde  := null;
    new.afastamento_motivo := null;
    new.afastado_por       := null;
  end if;
  return new;
end $$;

drop trigger if exists trg_afastamento on public.integrantes;
create trigger trg_afastamento
  before update of status on public.integrantes
  for each row execute function public.tratar_afastamento();

-- ---- Baixa de mensalidade lança no caixa automaticamente ----
create or replace function public.lancar_mensalidade_no_caixa()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_nome text;
begin
  if new.pago and not coalesce(old.pago,false) then
    select nome_completo into v_nome from public.integrantes where id = new.integrante_id;
    insert into public.caixa (tipo, descricao, valor, data, mensalidade_id, categoria, automatico)
    values ('Entrada',
            'Mensalidade ' || new.referencia || ' - ' || coalesce(v_nome,'#'||new.integrante_id),
            new.valor, coalesce(new.data_pagamento, current_date),
            new.id, 'Mensalidades', true);
  end if;
  return new;
end $$;

-- ---- Geração mensal em lote ----
-- A regra de quem é cobrado fica no BANCO, não na tela: assim não há risco de
-- a interface e o servidor discordarem sobre quem deve pagar.
create or replace function public.gerar_mensalidades(
  p_referencia text, p_valor numeric default 40.00, p_dia_venc int default 10)
returns table (criadas int, ja_existiam int, pulados_afastados int)
language plpgsql security definer set search_path = public as $$
declare v_ano int; v_mes int; v_venc date; v_antes int; v_depois int; v_alvos int; v_afast int;
begin
  if not public.tem_permissao('editar_financeiro') then
    raise exception 'Você não tem permissão para gerar mensalidades';
  end if;
  if p_referencia !~ '^\d{4}-\d{2}$' then
    raise exception 'Referência inválida: use o formato AAAA-MM';
  end if;

  v_ano := split_part(p_referencia,'-',1)::int;
  v_mes := split_part(p_referencia,'-',2)::int;
  v_venc := least(make_date(v_ano, v_mes, greatest(1, least(p_dia_venc, 28))),
                  (make_date(v_ano, v_mes, 1) + interval '1 month - 1 day')::date);
  if p_dia_venc > 28 then
    v_venc := (make_date(v_ano, v_mes, 1) + interval '1 month - 1 day')::date;
  end if;

  select count(*) into v_antes from public.mensalidades where referencia = p_referencia;
  select count(*) into v_alvos from public.integrantes where status = 'Ativo';
  select count(*) into v_afast from public.integrantes where status = 'Afastado';

  insert into public.mensalidades (integrante_id, referencia, vencimento, valor)
  select i.id, p_referencia, v_venc, p_valor
    from public.integrantes i where i.status = 'Ativo'
  on conflict (integrante_id, referencia) do nothing;

  select count(*) into v_depois from public.mensalidades where referencia = p_referencia;
  return query select (v_depois - v_antes), (v_alvos - (v_depois - v_antes)), v_afast;
end $$;

-- ---- Estorno ----
-- Sem isto, um clique errado deixaria dinheiro fantasma no saldo para sempre.
create or replace function public.estornar_pagamento(p_mensalidade_id bigint)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not public.tem_permissao('editar_financeiro') then
    raise exception 'Você não tem permissão para estornar pagamentos';
  end if;
  delete from public.caixa where mensalidade_id = p_mensalidade_id and automatico;
  update public.mensalidades
     set pago = false, data_pagamento = null, forma_pagamento = null
   where id = p_mensalidade_id;
end $$;

revoke execute on function public.gerar_mensalidades(text, numeric, int) from public, anon;
revoke execute on function public.estornar_pagamento(bigint) from public, anon;
grant  execute on function public.gerar_mensalidades(text, numeric, int) to authenticated;
grant  execute on function public.estornar_pagamento(bigint) to authenticated;

-- ---- Visões ----
drop view if exists public.vw_dashboard;
create view public.vw_dashboard with (security_invoker = true) as
  select
    (select count(*) from public.integrantes where status = 'Ativo')    as total_integrantes,
    (select count(*) from public.integrantes where status = 'Afastado') as total_afastados,
    -- canceladas por afastamento ficam fora da conta: senão a adimplência
    -- cairia sem ninguém ter deixado de pagar
    (select coalesce(round(100.0 * count(*) filter (where pago) / nullif(count(*),0), 1), 0)
       from public.mensalidades
      where referencia = to_char(current_date,'YYYY-MM') and not cancelada) as percentual_pagas,
    (select count(*) from public.mensalidades
      where referencia = to_char(current_date,'YYYY-MM')
        and not cancelada and not pago)                                 as pendentes_mes,
    (select coalesce(sum(case when tipo = 'Entrada' then valor else -valor end), 0)
       from public.caixa)                                               as saldo_caixa,
    (select nome from public.eventos where data >= current_date order by data limit 1) as proximo_evento_nome,
    (select data from public.eventos where data >= current_date order by data limit 1) as proximo_evento_data;

create or replace view public.vw_extrato_caixa with (security_invoker = true) as
  select c.*,
         sum(case when c.tipo = 'Entrada' then c.valor else -c.valor end)
           over (order by c.data, c.id rows between unbounded preceding and current row) as saldo_acumulado
    from public.caixa c;
