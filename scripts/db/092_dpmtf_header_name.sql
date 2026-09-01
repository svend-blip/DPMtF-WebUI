-- 092: The main heading carries the product's actual name.
--
-- Human correction 2026-09-01: the UI header read "Deterministic Prompt
-- – MockUp to Finalised" — an obsolete expansion. The canonical name is
--   DPMtF — Deterministic Process Management to Finalisation
-- It is a proper name, so every locale carries the identical string;
-- es-ES and el-GR already did (fixed earlier by hand), en-US, da-DK,
-- de-DE and sv-SE still carried the old text. ui_labels.default_text
-- was already correct — only the translation layer, which the 4-layer
-- i18n API actually returns, was stale.
--
-- The init_db.py seed (INSERT OR REPLACE, seed-owned) is corrected in
-- the same change set; this migration fixes databases that will not
-- re-run init_db.
--
-- Idempotent: the UPDATE converges on the canonical string; re-running
-- changes nothing.

UPDATE ui_label_translations
SET translated_text = 'DPMtF — Deterministic Process Management to Finalisation',
    updated_at = datetime('now')
WHERE label_id = 'LBL-1000008'
  AND translated_text <> 'DPMtF — Deterministic Process Management to Finalisation';
