-- Rollback 036: remove all es-ES translations.
DELETE FROM ui_label_translations WHERE locale = 'es-ES';
