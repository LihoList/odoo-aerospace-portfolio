-- Reconciliation snapshot: run before and after every copy/restore/upgrade and diff the output.
\pset footer off
\echo ## counts
select 'res_partner' as metric, count(*)::text as value from res_partner
union all select 'res_partner_active', count(*)::text from res_partner where active
union all select 'product_product', count(*)::text from product_product
union all select 'stock_lot', count(*)::text from stock_lot
union all select 'stock_move_done', count(*)::text from stock_move where state='done'
union all select 'stock_move_all', count(*)::text from stock_move
union all select 'stock_quant_rows_internal', count(*)::text from stock_quant q join stock_location l on l.id=q.location_id where l.usage='internal'
union all select 'stock_quant_qty_internal_total', round(sum(q.quantity),4)::text from stock_quant q join stock_location l on l.id=q.location_id where l.usage='internal'
union all select 'aero_outtime_event', count(*)::text from aero_outtime_event
union all select 'ir_attachment_file', count(*)::text from ir_attachment where store_fname is not null;
\echo ## aero_ncr by state
select state, count(*) from aero_ncr group by state order by state;
\echo ## mrp_production by state
select state, count(*) from mrp_production group by state order by state;
\echo ## purchase_order by state
select state, count(*) from purchase_order group by state order by state;
\echo ## stock_quant sum(quantity) by product + internal location
select coalesce(p.default_code, '') as default_code, p.id as product_id, l.complete_name as location, round(sum(q.quantity),4) as qty
  from stock_quant q
  join stock_location l on l.id = q.location_id
  join product_product p on p.id = q.product_id
 where l.usage = 'internal'
 group by p.id, p.default_code, l.complete_name
 order by p.id, l.complete_name;
