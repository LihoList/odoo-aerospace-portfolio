-- Workaround applied between the 17->18 and 18->19 OpenUpgrade steps (rehearsal finding).
-- openupgradelib 3.13.7 openupgrade_180.convert_company_dependent() copies 17's ir_property.value_integer
-- for boolean fields into the 18 jsonb column as a number ({"1": 1}). Odoo 18 reads it; Odoo 19 casts
-- (jsonb)::bool and fails with "cannot cast jsonb numeric to type boolean".
-- Rewrite numeric values of every boolean company_dependent field as jsonb booleans.
DO $$
DECLARE f record; n integer;
BEGIN
  FOR f IN
    SELECT m.model, fl.name AS col, replace(m.model, '.', '_') AS tbl
      FROM ir_model_fields fl JOIN ir_model m ON m.id = fl.model_id
     WHERE fl.ttype = 'boolean' AND fl.company_dependent AND fl.store
  LOOP
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = f.tbl AND column_name = f.col) THEN
      EXECUTE format($q$
        UPDATE %I SET %I = (
          SELECT jsonb_object_agg(key, CASE WHEN jsonb_typeof(value) = 'number'
                                            THEN to_jsonb((value #>> '{}')::numeric <> 0) ELSE value END)
            FROM jsonb_each(%I))
         WHERE %I IS NOT NULL AND jsonb_typeof(%I) = 'object'
           AND EXISTS (SELECT 1 FROM jsonb_each(%I) e WHERE jsonb_typeof(e.value) = 'number')$q$,
        f.tbl, f.col, f.col, f.col, f.col, f.col);
      GET DIAGNOSTICS n = ROW_COUNT;
      RAISE NOTICE '%.%: % rows fixed', f.tbl, f.col, n;
    END IF;
  END LOOP;
END $$;
