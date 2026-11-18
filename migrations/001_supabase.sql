-- Вставьте весь файл в Supabase Dashboard > SQL Editor > New query > Run.
-- Таблицы и RPC доступны только серверному service_role. Публичного доступа нет.
begin;
create table if not exists public.orders (
  id text primary key,
  request_key uuid not null unique,
  fingerprint text not null,
  payload_json jsonb not null,
  status text not null default 'awaiting_photos',
  photos_cleaned boolean not null default false,
  completed_at double precision,
  completed_by text,
  created_at timestamptz not null default now()
);
create table if not exists public.notification_logs (
  id bigint generated always as identity primary key,
  order_id text not null references public.orders(id),
  channel text not null check (channel in ('telegram','email')),
  status text not null default 'pending',
  attempts integer not null default 0,
  next_at double precision not null default 0,
  leased_until double precision not null default 0,
  progress jsonb not null default '{}'::jsonb,
  last_error text,
  unique(order_id,channel)
);
create index if not exists notification_pending on public.notification_logs(status,next_at);
alter table public.orders enable row level security;
alter table public.notification_logs enable row level security;
revoke all on public.orders, public.notification_logs from anon, authenticated;
grant all on public.orders, public.notification_logs to service_role;
grant usage, select on sequence public.notification_logs_id_seq to service_role;

create or replace function public.create_order(p_payload jsonb, p_request_key uuid, p_fingerprint text, p_channels text[])
returns jsonb language plpgsql security definer set search_path='' as $$
declare existing public.orders; was_created boolean := false;
begin
  insert into public.orders(id,request_key,fingerprint,payload_json)
    values(p_payload->>'id',p_request_key,p_fingerprint,p_payload)
    on conflict(request_key) do nothing returning * into existing;
  if found then
    was_created := true;
    insert into public.notification_logs(order_id,channel,status)
      select existing.id,c,case when c=any(p_channels) then 'pending' else 'skipped' end
      from unnest(array['telegram','email']) as c;
  else
    select * into existing from public.orders where request_key=p_request_key;
    if existing.fingerprint<>p_fingerprint then return jsonb_build_object('conflict',true); end if;
  end if;
  return jsonb_build_object('order',to_jsonb(existing),'created',was_created);
end $$;

create or replace function public.claim_notifications()
returns setof public.notification_logs language sql security definer set search_path='' as $$
  update public.notification_logs n set status='processing', attempts=n.attempts+1,
    leased_until=extract(epoch from now())+300
  where n.id in (
    select j.id from public.notification_logs j join public.orders o on o.id=j.order_id
    where o.status not in ('awaiting_photos','upload_failed')
      and j.status not in ('sent','skipped') and j.next_at<=extract(epoch from now())
      and j.leased_until<extract(epoch from now())
    order by j.id for update of j skip locked limit 2
  ) returning n.*;
$$;

create or replace function public.public_stats()
returns jsonb language sql security definer set search_path='' as $$
  select jsonb_build_object('completed_orders',count(*),'source','database')
  from public.orders where status='completed';
$$;
create or replace function public.cleanup_candidates()
returns setof public.orders language sql security definer set search_path='' as $$
  select o.* from public.orders o where not o.photos_cleaned
    and o.status not in ('awaiting_photos','upload_failed')
    and not exists (select 1 from public.notification_logs n where n.order_id=o.id and n.status not in ('sent','skipped'))
  order by o.created_at limit 20;
$$;
revoke all on function public.create_order(jsonb,uuid,text,text[]) from public,anon,authenticated;
revoke all on function public.claim_notifications() from public,anon,authenticated;
revoke all on function public.public_stats() from public,anon,authenticated;
revoke all on function public.cleanup_candidates() from public,anon,authenticated;
grant execute on function public.create_order(jsonb,uuid,text,text[]) to service_role;
grant execute on function public.claim_notifications() to service_role;
grant execute on function public.public_stats() to service_role;
grant execute on function public.cleanup_candidates() to service_role;

-- Закрытый временный буфер вложений для повторной доставки после перезапуска Render.
-- Объекты удаляет приложение через Storage API после отправки в оба канала.
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('order-photos','order-photos',false,8388608,array['image/jpeg'])
on conflict(id) do nothing;
commit;
