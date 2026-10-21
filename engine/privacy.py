"""The privacy notice. The same sentence lives in web/src/privacy.ts; a test keeps them identical."""

PRIVACY_NOTICE = 'Do not upload personal information. In live mode, text you enter is sent to OpenAI (US) for processing and is retained by OpenAI under its API data policy (https://openai.com/policies/api-data-usage-policies); Batatis deletes its own stored case data and files after 7 days or on request.'
# The response header and the JSON meta notice are this same sentence.
PII_NOTICE = PRIVACY_NOTICE


def assistant_notice(provider: str) -> str:
    name = 'Anthropic' if provider == 'anthropic' else 'OpenAI'
    return (f'AI help explains information and administrative completeness; it does not determine technical correctness. '
            f'In live mode, your question, recent chat and selected application context are sent to {name}. '
            'Avoid personal information. Batatis does not store this assistant chat; stored applications and '
            'their messages are deleted after 7 days or when the application is deleted.')
