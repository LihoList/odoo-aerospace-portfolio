\echo == ir_mail_server (id,name,host,active,has_user,has_pass)
select id,name,smtp_host,active,smtp_user is not null,smtp_pass is not null from ir_mail_server order by id;
\echo == ir_cron active/inactive
select active,count(*) from ir_cron group by active order by active;
\echo == ir_cron still active
select c.id, a.name->>'en_US' from ir_cron c join ir_act_server a on a.id=c.ir_actions_server_id where c.active;
\echo == config params
select key, case when key='database.secret' then left(value,6)||'...' else value end from ir_config_parameter where key in ('database.is_neutralized','database.secret','mail.web_push_vapid_private_key','mail.web_push_vapid_public_key','mail.sfu_server_key') order by key;
\echo == neutralize banner view
select key,active from ir_ui_view where key='web.neutralize_banner';
\echo == payment_provider states
select state,count(*) from payment_provider group by state;
\echo == iap_account tokens
select id, service_name, right(account_token,10) from iap_account;
\echo == fetchmail / devices / mail_template with server
select (select count(*) from fetchmail_server where active) fetchmail_active, (select count(*) from mail_partner_device) devices, (select count(*) from mail_template where mail_server_id is not null) tmpl_with_server;
