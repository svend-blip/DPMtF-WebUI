-- 051: Rev_Imple moves from glm-air-derestricted-local to
-- qwen35-uncensored-local (Human decision 2026-08-14).
--
-- The alias is served by llama.cpp on port 8081 (the allocator's
-- models.yaml carries the full runtime config: Q6_K weights, 65536
-- context — 131072 OOM'ed on the 32 GB card — q8_0 KV cache, 4 expert
-- layers on CPU, temp 0.6). Rev_Supervisor keeps
-- glm-air-derestricted-local on port 8080; the two aliases now differ,
-- so dispatch stops the outgoing model before starting the incoming one.
--
-- Idempotent: the UPDATE converges on the same value.

UPDATE bridge_roles
   SET default_model_alias = 'qwen35-uncensored-local'
 WHERE role_key = 'Rev_Imple'
   AND default_model_source = 'model_allocator';
