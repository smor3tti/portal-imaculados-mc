-- =====================================================================
-- 04 — Atualizações aplicadas entre ago/2026 e out/2026
-- Exportado do histórico de migrações do Supabase em 09/11/2026.
-- Rode DEPOIS de 01, 02 e 03. Tudo aqui é idempotente (pode rodar de novo).
-- =====================================================================


-- ---------------------------------------------------------------------
-- 20260807190410 · vincular conta nova ao integrante
-- ---------------------------------------------------------------------
-- Quando alguém cria conta no portal, procuramos um integrante com o mesmo
-- e-mail da ficha e ligamos automaticamente, já com o cargo correto.
-- Se não houver correspondência, o perfil nasce INATIVO e sem cargo de acesso:
-- a diretoria precisa liberar manualmente na aba Acessos.
create or replace function public.vincular_conta_nova()
returns trigger language plpgsql security definer set search_path = public as $$
declare v_integrante public.integrantes%rowtype;
begin
  select * into v_integrante
    from public.integrantes
   where lower(trim(email)) = lower(trim(new.email))
     and id not in (select integrante_id from public.perfis where integrante_id is not null)
   limit 1;

  if found then
    insert into public.perfis (user_id, integrante_id, cargo, ativo)
    values (new.id, v_integrante.id, v_integrante.cargo, true)
    on conflict (user_id) do nothing;
  else
    insert into public.perfis (user_id, integrante_id, cargo, ativo)
    values (new.id, null, 'Próspero', false)
    on conflict (user_id) do nothing;
  end if;

  return new;
end $$;

drop trigger if exists trg_vincular_conta_nova on auth.users;
create trigger trg_vincular_conta_nova
  after insert on auth.users
  for each row execute function public.vincular_conta_nova();


-- ---------------------------------------------------------------------
-- 20260807225746 · imagem nos comunicados
-- ---------------------------------------------------------------------
-- Caminho do arquivo dentro do Storage (não a URL completa: assim o bucket
-- pode mudar de nome ou de visibilidade sem quebrar os registros antigos).
alter table public.comunicados
  add column if not exists imagem_path text;

comment on column public.comunicados.imagem_path is
  'Caminho da imagem no bucket comunicados do Storage. Nulo quando o aviso não tem imagem.';

-- Bucket público: a imagem de um comunicado é para ser vista por todos os
-- integrantes, e servir arquivo público é bem mais rápido (cache do CDN).
-- Nada sensível deve ir aqui — atas e contratos continuam no bucket privado.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('comunicados', 'comunicados', true, 5242880,
        array['image/jpeg','image/png','image/webp','image/gif'])
on conflict (id) do update
  set public = true,
      file_size_limit = 5242880,
      allowed_mime_types = array['image/jpeg','image/png','image/webp','image/gif'];


-- ---------------------------------------------------------------------
-- 20260807225758 · políticas do Storage para comunicados
-- (a política de LEITURA foi substituída depois — ver 20261025212158)
-- ---------------------------------------------------------------------
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


-- ---------------------------------------------------------------------
-- 20260807230244 · imagem nos eventos
-- ---------------------------------------------------------------------
alter table public.eventos
  add column if not exists imagem_path text;

comment on column public.eventos.imagem_path is
  'Caminho da imagem no bucket eventos do Storage. Nulo quando o evento não tem cartaz/foto.';

-- Bucket separado do de comunicados de propósito: assim quem pode publicar
-- evento mexe só nas imagens de evento, e vice-versa.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('eventos', 'eventos', true, 5242880,
        array['image/jpeg','image/png','image/webp','image/gif'])
on conflict (id) do update
  set public = true,
      file_size_limit = 5242880,
      allowed_mime_types = array['image/jpeg','image/png','image/webp','image/gif'];

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


-- ---------------------------------------------------------------------
-- 20260808121842 · blindagem das funções de gatilho
-- ---------------------------------------------------------------------
-- 1) search_path faltando
alter function public.situacao_mensalidade(public.mensalidades) set search_path = public;

-- 2) Funções de GATILHO estavam expostas como API pública.
-- Elas devem rodar apenas quando o banco dispara o trigger — nunca por chamada
-- direta de fora. Um visitante podia invocá-las via /rest/v1/rpc/.
revoke execute on function public.lancar_mensalidade_no_caixa() from public, anon, authenticated;
revoke execute on function public.tratar_afastamento()          from public, anon, authenticated;
revoke execute on function public.vincular_conta_nova()         from public, anon, authenticated;
revoke execute on function public.marcar_atualizacao()          from public, anon, authenticated;
revoke execute on function public.sincronizar_cargo()           from public, anon, authenticated;

-- situacao_mensalidade é auxiliar de leitura: quem já pode ver a mensalidade
-- pode calcular a situação dela, mas anon não tem nada a ver com isso.
revoke execute on function public.situacao_mensalidade(public.mensalidades) from public, anon;
grant  execute on function public.situacao_mensalidade(public.mensalidades) to authenticated;


-- ---------------------------------------------------------------------
-- 20260831161842 · bucket privado de Documentos
-- ---------------------------------------------------------------------
-- Faltava esta migração: a tabela public.documentos e o código do site já
-- referenciam o bucket 'documentos', mas ele nunca havia sido criado.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documentos', 'documentos', false, 15728640,
        array['application/pdf',
              'application/msword',
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              'application/vnd.ms-excel',
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              'image/jpeg','image/png','text/plain'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists documentos_arquivo_ler on storage.objects;
create policy documentos_arquivo_ler on storage.objects
  for select to authenticated using (bucket_id = 'documentos' and public.tem_permissao('ver_documentos'));

drop policy if exists documentos_arquivo_enviar on storage.objects;
create policy documentos_arquivo_enviar on storage.objects
  for insert to authenticated
  with check (bucket_id = 'documentos' and public.tem_permissao('editar_documentos'));

drop policy if exists documentos_arquivo_atualizar on storage.objects;
create policy documentos_arquivo_atualizar on storage.objects
  for update to authenticated
  using (bucket_id = 'documentos' and public.tem_permissao('editar_documentos'))
  with check (bucket_id = 'documentos' and public.tem_permissao('editar_documentos'));

drop policy if exists documentos_arquivo_excluir on storage.objects;
create policy documentos_arquivo_excluir on storage.objects
  for delete to authenticated using (bucket_id = 'documentos' and public.tem_permissao('editar_documentos'));


-- ---------------------------------------------------------------------
-- 20260831192923 · senha padrão com troca obrigatória
-- ---------------------------------------------------------------------
alter table public.perfis
  add column if not exists precisa_trocar_senha boolean not null default false;

comment on column public.perfis.precisa_trocar_senha is
  'true = conta criada pela diretoria com senha padrão; a pessoa precisa trocar antes de continuar usando o portal.';

-- RPC que a própria pessoa chama, logada, depois de trocar a senha no Auth.
-- security definer só para poder atualizar a própria linha (a policy de UPDATE
-- de perfis exige permissão de gerenciar_acessos); sempre restrito a auth.uid().
create or replace function public.concluir_troca_senha_obrigatoria()
returns void
language plpgsql security definer set search_path = public as $$
begin
  update public.perfis set precisa_trocar_senha = false where user_id = auth.uid();
end $$;


-- ---------------------------------------------------------------------
-- 20260831195707 · valor padrão da mensalidade = R$ 50,00
-- (versão sem o status Suspenso; a 05 não altera esta função porque ela
--  já só cobra quem está 'Ativo')
-- ---------------------------------------------------------------------
create or replace function public.gerar_mensalidades(
  p_referencia text, p_valor numeric default 50.00, p_dia_venc int default 10)
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


-- ---------------------------------------------------------------------
-- 20261019204533 · hardening de search_path e revoke de anon
-- ---------------------------------------------------------------------
alter function public.vincular_conta_nova() set search_path = public;
revoke execute on function public.concluir_troca_senha_obrigatoria() from anon;
revoke execute on function public.concluir_troca_senha_obrigatoria() from public;
grant  execute on function public.concluir_troca_senha_obrigatoria() to authenticated;


-- ---------------------------------------------------------------------
-- 20261025211802 · anexar_comprovante valida o caminho do arquivo
-- ---------------------------------------------------------------------
create or replace function public.anexar_comprovante(p_mensalidade_id bigint, p_caminho text)
 returns void
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare v_meu bigint; v_dono bigint; v_pago boolean; v_cancelada boolean; v_fin boolean;
begin
  v_meu := public.meu_integrante_id();
  if v_meu is null then
    raise exception 'Sua conta ainda não está ligada a um integrante';
  end if;

  select integrante_id, pago, cancelada
    into v_dono, v_pago, v_cancelada
    from public.mensalidades where id = p_mensalidade_id;

  if v_dono is null then
    raise exception 'Mensalidade não encontrada';
  end if;

  v_fin := public.tem_permissao('editar_financeiro');

  -- o financeiro pode anexar por qualquer um (ex.: recebeu o print no WhatsApp)
  if v_dono <> v_meu and not v_fin then
    raise exception 'Você só pode enviar comprovante da sua própria mensalidade';
  end if;

  -- quem não é do financeiro só pode apontar para a própria pasta no Storage
  if not v_fin and (p_caminho is null
                    or left(p_caminho, length(v_meu::text) + 1) <> v_meu::text || '/'
                    or p_caminho like '%..%') then
    raise exception 'Caminho do comprovante inválido';
  end if;

  if v_pago then
    raise exception 'Esta mensalidade já está paga';
  end if;
  if v_cancelada then
    raise exception 'Esta mensalidade está cancelada';
  end if;

  update public.mensalidades
     set comprovante_path       = p_caminho,
         comprovante_enviado_em = now(),
         recusado_em            = null,   -- reenvio limpa a recusa anterior
         motivo_recusa          = null
   where id = p_mensalidade_id;
end $function$;


-- ---------------------------------------------------------------------
-- 20261025212158 · restringe a LISTAGEM dos buckets públicos
-- (a imagem continua abrindo pela URL pública; só não dá para listar o bucket)
-- ---------------------------------------------------------------------
drop policy if exists comunicados_img_ler on storage.objects;
drop policy if exists eventos_img_ler on storage.objects;

create policy comunicados_img_ler on storage.objects
  for select to authenticated
  using (bucket_id = 'comunicados' and public.tem_permissao('editar_comunicados'));

create policy eventos_img_ler on storage.objects
  for select to authenticated
  using (bucket_id = 'eventos' and public.tem_permissao('editar_eventos'));
