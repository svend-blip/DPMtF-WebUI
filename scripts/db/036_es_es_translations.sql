-- 036: es-ES translations for every active label.
--
-- 2026-08-08 the coding standard moved from two mandatory locales
-- (da-DK, en-US) to four (en-US, da-DK, de-DE, es-ES). This migration
-- closes Father's measured gap: validate_i18n_completeness reported
-- 334/334 active labels missing es-ES.
--
-- Idempotent per row (NOT EXISTS guard — the table has no unique index
-- on label_id+locale). Joins on label_key, which is unique among active
-- labels. Rows for inactive labels are not created; sv-SE/el-GR rows
-- are untouched (optional extras per the standard).

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_aliases' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '¿Eliminar ''{name}''?', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_confirm_delete' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Eliminar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_delete' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Detalle', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_detail' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias de clientes', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_client_aliases' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Clientes', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_clients' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Directorio de configuración', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_config_dir' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Contexto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_context' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias predeterminado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_default_alias' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Política de ciclo de vida', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_lifecycle' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Modelo real', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ruta del modelo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_model_path' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nombre', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Perfil de runtime', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_field_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No se pudo cargar la configuración del allocator', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_load_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nombre obligatorio', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_name_required' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '+ Nuevo alias', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_new_alias' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '+ Nuevo rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_new_role' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Perfiles de runtime (solo lectura)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_profiles' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Roles', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_roles' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Guardar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_save' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Guardado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_saved' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Seleccione un alias o rol para editar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_alloc_select_hint' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Puerto de la aplicación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_app_port' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Perfil de la aplicación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_app_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '(resuelto automáticamente desde el paso del flujo)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_auto_resolved_flow_step' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Activo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_active' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comando agregado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_aggregated_cmd' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Estado del allocator', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_allocator_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Adjuntar tmux', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_attach_tmux' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '(autocompletado)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_auto_filled' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Cancelar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_cancel' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Modelo en la nube', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_cloud_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nube', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_cloud_option' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '¿Detener el runtime del allocator para ''{alias}''?', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_confirm_stop' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Plantilla de contenido', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_content_template' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Convenciones', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_conventions_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Creado correctamente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_created' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'default_model', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias de modelo predeterminado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_model_alias' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fuente de modelo predeterminada', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_model_source' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'default_provider', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_provider' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'default_runtime', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_default_runtime' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Eliminar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_delete' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Eliminado correctamente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_deleted' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Mensaje de error', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_deliver_error_msg' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Directorio de entregables', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_deliverable_dir' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Patrón de entregables', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_deliverable_pattern' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Editar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_edit' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Editar flujo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_edit_flow' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Editar rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_edit_role' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Exportar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_export' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Exportar todo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_export_all' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Exportar todos los datos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_export_all_data' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Exportar flujos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_export_flows' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Exportar roles', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_export_roles' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Añadir flujo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_add' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comando de adjuntar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_attach_command' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecute "Adjuntar tmux" primero para crear esta sesión y luego pegue el comando en una terminal.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_attach_hint' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Autocompletado activado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_auto_complete' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Descripción', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_description' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Predeterminado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_is_default' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Clave del flujo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_key' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nombre', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Orden de pasos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_step_order' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ruta del proyecto destino', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_target_project' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ruta absoluta al repositorio en el que trabajan los roles de este flujo. Debe existir. Déjela vacía para flujos que operan sobre este proyecto.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_target_project_help' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Vacío = este proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flow_target_project_placeholder' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Flujos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_flows_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Archivo de gobernanza', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_governance_file' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Política de GPU', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_gpu_policy' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Inactivo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_inactive' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Última validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_last_validated' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Máx. tokens de salida', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_max_output_tokens' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Predeterminado / heredar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_model_source_default' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tipo de modelo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_model_type' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No hay flujos configurados', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_no_flows' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No hay roles configurados', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_no_roles' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No está en ejecución', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_not_running' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Modelo de Ollama', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_ollama_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ollama', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_ollama_option' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Configuración del Bridge', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_panel_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'PID', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_pid' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Puerto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_port' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Script post-dispatch', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_post_dispatch_script' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Script pre-dispatch', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_pre_dispatch_script' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Actualizar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_refresh' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Renombrar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_rename' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Sin cambios', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_rename_invalid' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Renombrado correctamente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_renamed' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Siempre', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_restart_always' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ninguno', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_restart_none' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'En caso de fallo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_restart_on_failure' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'En caso de éxito', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_restart_on_success' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Añadir rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_role_add' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Clave del rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_role_key' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tipo de rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_role_type' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Roles', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_roles_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Regla de convención', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_rule_key' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'En ejecución', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_running' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Estado del runtime', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_runtime_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Guardar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_save' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Script post-dispatch', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_script_post' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Script pre-dispatch', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_script_pre' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Seleccionar flujo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_select_flow' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Script de configuración', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_setup_script' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Iniciar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_start' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comando de inicio', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_start_cmd' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Sufijo del comando de inicio', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_start_cmd_suffix' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Configuración del bridge disponible', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_status_available' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Añadir paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_add' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Encadenar automáticamente al siguiente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_auto_chain' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Añadir/editar paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_form_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Rol de origen', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_from_role' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Clave del paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_key' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias de modelo del paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_model_alias' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fuente de modelo del paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_model_source' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Heredar del rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_model_source_inherit' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Quitar paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_remove' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Orden', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_sort_order' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Rol de destino', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_to_role' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Requerir validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_step_validation_required' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Pasos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_steps_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Detener', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_stop' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Script de desmontaje', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_teardown_script' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Sesión de tmux', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_tmux_session' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Modo push de Trade-MCP', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_trade_mcp_push_mode' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Actualizado correctamente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_updated' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Usar el perfil de máquina para los comandos de inicio', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_use_machine_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Validar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_validate_allocator' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_validation_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'OK', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_validation_ok' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Esquema de validación (array JSON)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_validation_schema' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_validation_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Advertencia', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_validation_warning' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Este proyecto (Father)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_workdir_father' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Dónde inicia la sesión de código de este rol. Los workers de la cadena siguen la ruta del proyecto destino del flujo; supervisores y arquitectos permanecen en este proyecto.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_workdir_help' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Directorio de trabajo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_workdir_mode' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Proyecto destino del flujo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_bridge_workdir_target' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Añadir paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_add_step' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Asignar ID de handoff', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_assign_handoff_id' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Cerrar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_close_drawer' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '¡Copiado!', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_copied' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Copiar comando', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_copy_command' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error al copiar — seleccione y copie manualmente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_copy_failed' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Copiar prompt', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_copy_prompt' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Crear', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_create' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Crear plan de proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_create_project_plan' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Entregar al Bridge', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_deliver_to_bridge' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Generar vista previa del siguiente prompt', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_generate_prompt' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Actualizar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_refresh' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecutar validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_run_validation' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Guardar prompt generado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_save_prompt' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Configuración del sistema', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_btn_system_setup' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nube', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_cmp_cloud' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'ID', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_cmp_id' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Local', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_cmp_local' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tarea', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_cmp_task' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nivel', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_cmp_tier' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ganador', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_cmp_winner' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Dur. media', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_avg_dur' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Duración media', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_avg_duration' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Mejor modelo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_best_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Restricciones', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_constraints' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Corr', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_corrections' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Coste', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_cost' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Duración', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_duration' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Archivos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_files' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '1.er intento', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_first_try' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Última ejecución', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_last_run' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Modelo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_model' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Notas', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_notes' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'ID de patrón', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_pattern_id' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fase', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_phase' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_project' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Resultado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_result' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Regla', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_rule' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'ID de ejecución', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_run_id' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecuciones', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_runs' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Estado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tasa de éxito', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_success_rate' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Exitosas / Total', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_successful_total' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Marca de tiempo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_col_timestamp' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Errores de validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compile_validation_errors' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Crear nueva WebUI', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_create_webui_btn' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Este campo es obligatorio', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_field_required' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Archivos de gobernanza a crear en docs/dpmtf/:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_governance_reminder' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nueva webui', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_new_webui_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Puerto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_new_webui_port' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Título', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_new_webui_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Abrir WebUI', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_open_webui' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error de script', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_script_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Iniciar servidor WebUI', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_start_server_btn' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Proyecto WebUI creado correctamente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_compiler_webui_created' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '¿Eliminar el paso #{stepId}?', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_confirm_delete_step' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '¿Detener todas las sesiones de tmux de ''{flowKey}''?', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_confirm_stop_tmux_sessions' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Entregando...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_deliver_in_progress' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No hay handoff listo. Asigne primero un ID de handoff.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_deliver_no_handoff' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Handoff {ID} entregado a {TO}', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_deliver_success' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comando de dispatch:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_dispatch_command' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Conjunto de datos inicial', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_bootstrap' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecuciones comparativas', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_comparisons' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Vista previa del diseño de la base de datos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_db_layout' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Registro de endpoints', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_endpoint_registry' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Etiquetas de UI / i18n', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_i18n' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Slots de diseño', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_layout_slots' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Seguridad / Permisos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_drawer_security' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Aún no hay secuencias de prompts. Cree la primera secuencia para empezar a planificar prompts pequeños para Claude Code.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_empty_sequences' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Aún no hay pasos. Añada pasos a la secuencia para generar prompts.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_empty_steps' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error: ', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_error_prefix' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Archivo escrito:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_handoff_file_written' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Handoff {ID} listo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_handoff_ready' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Deterministic Prompt – MockUp to Finalised', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_heading_main' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobando el perfil de máquina...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_checking' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Falta el perfil de máquina — créelo en Configuración del sistema antes de activar.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_missing' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'El perfil de máquina tiene un error de JSON — corríjalo antes de activar.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_parse_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'schema_version del perfil de máquina no coincide — actualice el perfil antes de activar.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_mp_schema_mismatch' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error de red: ', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_network_error_prefix' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Aún no hay prompts generados. Genere y guarde prompts para verlos aquí.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_no_prompts_yet' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Aún no hay ejecuciones de flujo.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_no_workflow_runs' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Notas', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_notes' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '(opcional — seleccione para dispatch de BridgeV002)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_optional_select_for_bridgev002' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'DPMtF WebUI', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_page_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Estado de la base de datos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_panel_db_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tasas de acierto de prompts', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_panel_hitrates' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Estado de fases', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_panel_phase_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Planificación de nuevo proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_panel_project_planning' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Planificador de secuencias de prompts', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_panel_prompt_sequences' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Plantillas de prompts', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_panel_templates' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Patrones de implementación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_pat_heading' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'mywebui', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_placeholder_new_webui_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '9136', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_placeholder_new_webui_port' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Mi proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_placeholder_new_webui_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nombre del proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_project_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Historial de prompts / Archivo generado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_prompt_history' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Generar vista previa del siguiente prompt', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_prompt_preview' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Secuencia de prompts', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_prompt_sequence_select' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecuciones de prompts recientes', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_runs_heading' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Responsabilidad humana', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_section_human_resp' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Migración', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_section_migration' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Proyecto', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_section_project' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alcance', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_section_scope' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_section_validation' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Seleccione una secuencia...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_select_sequence' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Secuencias', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_sequence_count' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Secuencias', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_sequences' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'información de sesión no disponible', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_session_info_unavailable' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Asignando ID de handoff...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_assigning_id' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Compilando...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_compiling' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Completado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_completed' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error: ', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_error_prefix' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fallido', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_failed' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Cargando...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_loading' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Siguiente', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_next' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No hay datos disponibles.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_no_data' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Planificado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_planned' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Éxito', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_status_success' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Pasos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_step_count' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Pasos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_steps' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Carpeta de destino', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_target_folder' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Sesión tmux de destino', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_target_session' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Arquitecto — diseño y análisis (claude_architect)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_target_session_architect' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Implementador — ejecución de código (claude_implementer)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_target_session_implementor' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Revisión — validación y coordinación (claude_review)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_target_session_review' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Archivos permitidos (uno por línea):', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_allowed_files' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Captura', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_capture' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Haga clic para ver', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_click_to_view' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'SR en la nube', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_cloud_sr' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'SR en la nube:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_cloud_sr_label' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Compilar prompt', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_compile_prompt' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Prompt compilado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_compiled_prompt' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Restricciones (una por línea):', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_constraints' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tokens estimados:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_estimated_tokens' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Objetivo:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_goal' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Clave', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_key' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'SR local', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_local_sr' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'SR local:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_local_sr_label' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tasas de acierto por modelo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_model_hitrates' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nombre', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_name' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'ID de fase:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_phase_id' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Vista previa', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_preview' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ruta del proyecto:', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_project_path' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'ejecuciones', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_runs_count' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Adecuado para', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_suitable_for' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Plantillas', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_templates' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Nivel', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_tier' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Tokens (entrada/salida)', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_tokens' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comandos de validación (uno por línea):', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_tpl_validation_cmds' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error desconocido', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_unknown_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Sin reglas de validación.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_val_no_rules' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecutando validación...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'lbl_val_running' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '🧩 Model Allocator', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_allocator' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '📆 Diario', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_daily' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '📓 Diarios de trabajo', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_journals' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '🔄 Periódico', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_periodic' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '📊 Informes', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_reports' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', '⚙️ Configuración', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'pg_setup' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Mostrar fases completadas', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'phase_status.show_completed' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Proyectos existentes', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'sg_periodic_existing_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fase', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'sg_periodic_phase_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Planificación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'sg_periodic_planning_title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Vista previa de solo lectura desde /api/frontend-layout', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup.database_layout_preview.description' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Actualizar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup.database_layout_preview.refresh' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Vista previa del diseño de la base de datos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup.database_layout_preview.title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Slots de diseño', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup.layout_slots.title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Configuración del sistema', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup.title' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Heredar del rol', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_existing_unchanged' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Máquina', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_machine' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fuente de modelo predeterminada', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_machine_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_migration' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias de modelo predeterminado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_model_providers' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'No se devolvieron comprobaciones', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_no_checks' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Predeterminado / heredar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_no_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Advertencia', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_ollama_check' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Error de análisis de JSON en el perfil', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_parse_error' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Alias de modelo del paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_path_checks' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Validar', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_port_checks' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Perfil', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Listo. Haga clic en un botón de comprobación para ejecutar.', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_ready' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar binarios', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_binaries' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar ollama', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_ollama' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar rutas', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_paths' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar puertos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_ports' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar perfil', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_profile' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar proveedores', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_providers' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar secretos', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_secrets' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Comprobar tmux', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_run_tmux' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Ejecutando comprobaciones...', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_running' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Fuente de modelo del paso', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_runtime_config' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Esquema', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_schema' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Validación', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_secrets_check' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'Estado', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_status' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');

INSERT INTO ui_label_translations (label_id, locale, translated_text, is_active, created_at, updated_at)
SELECT l.label_id, 'es-ES', 'OK', 1, datetime('now'), datetime('now')
FROM ui_labels l WHERE l.label_key = 'system_setup_tmux_check' AND l.is_active = 1
AND NOT EXISTS (SELECT 1 FROM ui_label_translations x
  WHERE x.label_id = l.label_id AND x.locale = 'es-ES');
