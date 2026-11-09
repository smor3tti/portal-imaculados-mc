-- =====================================================================
-- 05 — Acessos, suspensão, artes de aniversário e novos cargos (09/11/2026)
-- Rode DEPOIS do 04. Idempotente: pode rodar de novo sem duplicar nada.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Administradores técnicos
-- Tabela com RLS ligado e SEM políticas: ninguém altera pelo portal
-- (nem quem tem gerenciar_acessos); só via SQL Editor / painel.
-- ---------------------------------------------------------------------
create table if not exists public.admins_tecnicos (
  user_id uuid primary key references auth.users(id) on delete cascade,
  criado_em timestamptz not null default now()
);
alter table public.admins_tecnicos enable row level security;
revoke all on public.admins_tecnicos from anon, authenticated;

-- Num banco novo, cadastre o seu usuário (troque o e-mail):
-- insert into public.admins_tecnicos(user_id)
--   select id from auth.users where email = 'SEU-EMAIL@exemplo.com'
-- on conflict do nothing;


-- ---------------------------------------------------------------------
-- Status de acesso (senha trocada, último login, última atividade)
-- Só administradores técnicos podem chamar.
-- ---------------------------------------------------------------------
create or replace function public.status_acessos()
returns table(user_id uuid, ultimo_login timestamptz, ultima_atividade timestamptz, sessoes int, precisa_trocar_senha boolean)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.admins_tecnicos a where a.user_id = (select auth.uid())) then
    raise exception 'Sem permissão para ver o status de acesso.' using errcode = '42501';
  end if;
  return query
    select p.user_id,
           u.last_sign_in_at,
           (select max(coalesce(s.refreshed_at, s.updated_at, s.created_at)) from auth.sessions s where s.user_id = p.user_id),
           (select count(*)::int from auth.sessions s where s.user_id = p.user_id and (s.not_after is null or s.not_after > now())),
           p.precisa_trocar_senha
      from public.perfis p
      join auth.users u on u.id = p.user_id;
end $$;

revoke all on function public.status_acessos() from public, anon;
grant execute on function public.status_acessos() to authenticated;


-- ---------------------------------------------------------------------
-- Presença online: canal privado 'portal-online' do Realtime,
-- só para contas ativas do portal.
-- ---------------------------------------------------------------------
drop policy if exists "presenca portal: ler" on realtime.messages;
create policy "presenca portal: ler" on realtime.messages
  for select to authenticated
  using (
    realtime.topic() = 'portal-online'
    and realtime.messages.extension in ('presence')
    and exists (select 1 from public.perfis p where p.user_id = (select auth.uid()) and p.ativo)
  );

drop policy if exists "presenca portal: anunciar" on realtime.messages;
create policy "presenca portal: anunciar" on realtime.messages
  for insert to authenticated
  with check (
    realtime.topic() = 'portal-online'
    and realtime.messages.extension in ('presence')
    and exists (select 1 from public.perfis p where p.user_id = (select auth.uid()) and p.ativo)
  );


-- ---------------------------------------------------------------------
-- Status 'Suspenso': bloqueia o acesso, derruba as sessões e para a
-- geração de novas mensalidades (gerar_mensalidades só cobra 'Ativo').
-- Mensalidades já em aberto CONTINUAM devidas.
-- ---------------------------------------------------------------------
alter table public.integrantes drop constraint if exists integrantes_status_check;
alter table public.integrantes add constraint integrantes_status_check
  check (status = any (array['Ativo','Afastado','Inativo','Suspenso']));

alter table public.integrantes
  add column if not exists suspensao_desde date,
  add column if not exists suspensao_motivo text;

create or replace function public.tratar_suspensao_campos()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.status = 'Suspenso' and coalesce(old.status,'') <> 'Suspenso' then
    new.suspensao_desde := coalesce(new.suspensao_desde, current_date);
  elsif new.status <> 'Suspenso' and coalesce(old.status,'') = 'Suspenso' then
    new.suspensao_desde  := null;
    new.suspensao_motivo := null;
  end if;
  return new;
end $$;

drop trigger if exists trg_suspensao_campos on public.integrantes;
create trigger trg_suspensao_campos before insert or update of status on public.integrantes
  for each row execute function public.tratar_suspensao_campos();

create or replace function public.tratar_suspensao_acesso()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.status = 'Suspenso' and coalesce(old.status,'') <> 'Suspenso' then
    update public.perfis p set ativo = false
     where p.integrante_id = new.id
       and not exists (select 1 from public.admins_tecnicos a where a.user_id = p.user_id);
    delete from auth.sessions s
     where s.user_id in (select p.user_id from public.perfis p where p.integrante_id = new.id)
       and not exists (select 1 from public.admins_tecnicos a where a.user_id = s.user_id);
  elsif new.status <> 'Suspenso' and coalesce(old.status,'') = 'Suspenso' then
    update public.perfis p set ativo = true where p.integrante_id = new.id;
  end if;
  return null;
end $$;

drop trigger if exists trg_suspensao_acesso on public.integrantes;
create trigger trg_suspensao_acesso after insert or update of status on public.integrantes
  for each row execute function public.tratar_suspensao_acesso();

create or replace function public.proteger_bloqueio_perfil()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.ativo is distinct from old.ativo then
    -- administrador técnico nunca é bloqueado
    if not new.ativo and exists (select 1 from public.admins_tecnicos a where a.user_id = new.user_id) then
      raise exception 'Esta conta é de administrador técnico e não pode ser bloqueada.' using errcode = '42501';
    end if;
    -- suspenso não volta por botão: tem que mudar o status na ficha
    if new.ativo and exists (select 1 from public.integrantes i where i.id = new.integrante_id and i.status = 'Suspenso') then
      raise exception 'Integrante suspenso. Para liberar o acesso, mude o status na ficha.' using errcode = '42501';
    end if;
    -- bloqueio manual também derruba as sessões abertas
    if not new.ativo then
      delete from auth.sessions s where s.user_id = new.user_id;
    end if;
  end if;
  return new;
end $$;

drop trigger if exists trg_proteger_bloqueio on public.perfis;
create trigger trg_proteger_bloqueio before update of ativo on public.perfis
  for each row execute function public.proteger_bloqueio_perfil();

revoke all on function public.tratar_suspensao_campos() from public, anon, authenticated;
revoke all on function public.tratar_suspensao_acesso() from public, anon, authenticated;
revoke all on function public.proteger_bloqueio_perfil() from public, anon, authenticated;


-- ---------------------------------------------------------------------
-- Artes de aniversário (uma por integrante por ano)
-- ---------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from public.permissoes_catalogo where chave = 'editar_artes_aniversario') then
    update public.permissoes_catalogo set ordem = ordem + 1 where ordem >= 12;
    insert into public.permissoes_catalogo(chave, label, grupo, ordem)
    values ('editar_artes_aniversario', 'Publicar artes de aniversário', 'Comunicados', 12);
  end if;
end $$;

update public.cargos
   set permissoes_padrao = array_append(permissoes_padrao, 'editar_artes_aniversario')
 where nome in ('Presidente','Vice Presidente','Diretor Geral','Diretor Disciplina','Diretor Social',
                'Diretor de Eventos','Tesoureiro','Secretário','Imprensa/Marketing')
   and not ('editar_artes_aniversario' = any(permissoes_padrao));

create table if not exists public.artes_aniversario (
  id bigserial primary key,
  integrante_id bigint not null references public.integrantes(id) on delete cascade,
  ano int not null check (ano between 2020 and 2100),
  caminho text not null,
  criado_em timestamptz not null default now(),
  criado_por uuid default auth.uid(),
  unique (integrante_id, ano)
);
alter table public.artes_aniversario enable row level security;

drop policy if exists artes_aniv_ler on public.artes_aniversario;
create policy artes_aniv_ler on public.artes_aniversario
  for select to authenticated using (public.tem_permissao('ver_dashboard'));
drop policy if exists artes_aniv_enviar on public.artes_aniversario;
create policy artes_aniv_enviar on public.artes_aniversario
  for insert to authenticated with check (public.tem_permissao('editar_artes_aniversario'));
drop policy if exists artes_aniv_atualizar on public.artes_aniversario;
create policy artes_aniv_atualizar on public.artes_aniversario
  for update to authenticated using (public.tem_permissao('editar_artes_aniversario'))
  with check (public.tem_permissao('editar_artes_aniversario'));
drop policy if exists artes_aniv_excluir on public.artes_aniversario;
create policy artes_aniv_excluir on public.artes_aniversario
  for delete to authenticated using (public.tem_permissao('editar_artes_aniversario'));

-- Bucket público (mesmo padrão de comunicados/eventos): a imagem abre pela
-- URL pública; listar, enviar e apagar só com a permissão.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('aniversarios', 'aniversarios', true, 5242880, array['image/jpeg','image/png','image/webp','image/gif'])
on conflict (id) do nothing;

drop policy if exists aniversarios_img_ler on storage.objects;
create policy aniversarios_img_ler on storage.objects for select to authenticated
  using (bucket_id = 'aniversarios' and public.tem_permissao('editar_artes_aniversario'));
drop policy if exists aniversarios_img_enviar on storage.objects;
create policy aniversarios_img_enviar on storage.objects for insert to authenticated
  with check (bucket_id = 'aniversarios' and public.tem_permissao('editar_artes_aniversario'));
drop policy if exists aniversarios_img_atualizar on storage.objects;
create policy aniversarios_img_atualizar on storage.objects for update to authenticated
  using (bucket_id = 'aniversarios' and public.tem_permissao('editar_artes_aniversario'))
  with check (bucket_id = 'aniversarios' and public.tem_permissao('editar_artes_aniversario'));
drop policy if exists aniversarios_img_excluir on storage.objects;
create policy aniversarios_img_excluir on storage.objects for delete to authenticated
  using (bucket_id = 'aniversarios' and public.tem_permissao('editar_artes_aniversario'));

-- Artes de ontem até daqui a 6 dias (horário de Brasília), para o destaque do Dashboard.
-- SECURITY DEFINER porque Próspero não lê 'integrantes', mas vê o dashboard.
create or replace function public.artes_aniversario_semana()
returns table(integrante_id bigint, nome_completo text, nome_no_colete text,
              aniversario date, caminho text, arte_id bigint)
language sql stable security definer set search_path = ''
as $$
  with hoje as (select (now() at time zone 'America/Sao_Paulo')::date d),
  aniv as (
    select i.id, i.nome_completo, i.nome_no_colete,
           make_date(a.ano,
                     extract(month from i.data_nascimento)::int,
                     least(extract(day from i.data_nascimento)::int,
                           extract(day from (make_date(a.ano, extract(month from i.data_nascimento)::int, 1)
                                             + interval '1 month - 1 day'))::int)) as dia,
           a.caminho, a.id as arte_id
      from public.artes_aniversario a
      join public.integrantes i on i.id = a.integrante_id
     where i.data_nascimento is not null
  )
  select x.id, x.nome_completo, x.nome_no_colete, x.dia, x.caminho, x.arte_id
    from aniv x, hoje h
   where public.tem_permissao('ver_dashboard')
     and x.dia between h.d - 1 and h.d + 6
   order by x.dia;
$$;
revoke all on function public.artes_aniversario_semana() from public, anon;
grant execute on function public.artes_aniversario_semana() to authenticated;

-- Aniversariantes dos próximos dias, mesmo virando o mês (tela de subir artes).
create or replace function public.aniversariantes_proximos(p_dias int default 14)
returns table(integrante_id bigint, nome_completo text, nome_no_colete text, aniversario date, tem_arte boolean)
language sql stable security definer set search_path = ''
as $$
  with hoje as (select (now() at time zone 'America/Sao_Paulo')::date d),
  base as (
    select i.id, i.nome_completo, i.nome_no_colete, i.data_nascimento, h.d
      from public.integrantes i, hoje h
     where i.status = 'Ativo' and i.data_nascimento is not null
  ),
  datas as (
    select b.*, case when (b.data_nascimento + ((extract(year from b.d) - extract(year from b.data_nascimento))::int * interval '1 year'))::date < b.d - 1
                     then (b.data_nascimento + ((extract(year from b.d) - extract(year from b.data_nascimento))::int + 1) * interval '1 year')::date
                     else (b.data_nascimento + ((extract(year from b.d) - extract(year from b.data_nascimento))::int * interval '1 year'))::date end as dia
      from base b
  )
  select x.id, x.nome_completo, x.nome_no_colete, x.dia,
         exists (select 1 from public.artes_aniversario a where a.integrante_id = x.id and a.ano = extract(year from x.dia)::int)
    from datas x
   where public.tem_permissao('editar_artes_aniversario')
     and x.dia between x.d - 1 and x.d + greatest(1, least(p_dias, 60))
   order by x.dia;
$$;
revoke all on function public.aniversariantes_proximos(int) from public, anon;
grant execute on function public.aniversariantes_proximos(int) to authenticated;


-- ---------------------------------------------------------------------
-- Novos cargos: Diretor Regional e Diretor de Expansão
-- ---------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from public.cargos where nome = 'Diretor Regional') then
    update public.cargos set ordem = ordem + 2 where ordem >= 7;
    insert into public.cargos (nome, ordem, e_diretoria, permissoes_padrao) values
      ('Diretor Regional', 7, true,
       array['ver_dashboard','ver_integrantes','ver_eventos','editar_eventos','ver_comunicados',
             'editar_comunicados','editar_artes_aniversario','ver_documentos']),
      ('Diretor de Expansão', 8, true,
       array['ver_dashboard','ver_integrantes','ver_eventos','ver_comunicados','editar_comunicados',
             'editar_artes_aniversario','ver_documentos','ver_solicitacoes','analisar_solicitacoes']);
  end if;
end $$;

create or replace function public.normalizar_cargo(p_texto text)
 returns text language sql immutable set search_path to 'public'
as $function$
  select case
    when p_texto is null or trim(p_texto) = '' then 'Próspero'
    when trim(p_texto) in (select nome from public.cargos) then trim(p_texto)
    when lower(public.unaccent_simples(p_texto)) like '%vice%'       then 'Vice Presidente'
    when lower(public.unaccent_simples(p_texto)) like '%presidente%' then 'Presidente'
    when lower(public.unaccent_simples(p_texto)) like '%regional%'   then 'Diretor Regional'
    when lower(public.unaccent_simples(p_texto)) like '%expans%'     then 'Diretor de Expansão'
    when lower(public.unaccent_simples(p_texto)) like '%geral%'      then 'Diretor Geral'
    when lower(public.unaccent_simples(p_texto)) like '%disciplina%' then 'Diretor Disciplina'
    when lower(public.unaccent_simples(p_texto)) like '%social%'     then 'Diretor Social'
    when lower(public.unaccent_simples(p_texto)) like '%evento%'     then 'Diretor de Eventos'
    when lower(public.unaccent_simples(p_texto)) like '%tesoureir%'  then 'Tesoureiro'
    when lower(public.unaccent_simples(p_texto)) like '%secretari%'  then 'Secretário'
    when lower(public.unaccent_simples(p_texto)) like '%conselheir%' then 'Conselheiro'
    when lower(public.unaccent_simples(p_texto)) like '%imprensa%'
      or lower(public.unaccent_simples(p_texto)) like '%marketing%'  then 'Imprensa/Marketing'
    when lower(public.unaccent_simples(p_texto)) like '%brasao%'     then 'Membro com Brasão'
    when lower(public.unaccent_simples(p_texto)) like '%prospero%'   then 'Próspero'
    else 'Próspero'
  end;
$function$;
