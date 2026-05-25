-- Change APIs only in SQL (no code edit required)
USE AngadTrading;
GO

-- OpenAI key
UPDATE dbo.api_config
SET config_value = 'sk-your-key-here', updated_at = SYSUTCDATETIME()
WHERE provider_code = 'openai' AND config_key = 'api_key';

-- Model
UPDATE dbo.api_config
SET config_value = 'gpt-4o-mini'
WHERE provider_code = 'openai' AND config_key = 'model_json';

-- Disable a provider
UPDATE dbo.api_providers SET is_enabled = 0 WHERE provider_code = 'openai';

-- View all API settings
SELECT p.provider_code, p.display_name, p.provider_type, c.config_key,
       CASE WHEN c.is_secret = 1 THEN '***' ELSE c.config_value END AS config_value
FROM dbo.api_providers p
LEFT JOIN dbo.api_config c ON c.provider_code = p.provider_code
ORDER BY p.provider_code, c.config_key;
