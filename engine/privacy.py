"""The privacy notice. The same sentence lives in web/src/privacy.ts; a test keeps them identical."""

PRIVACY_NOTICE = 'Batatis automatically removes the names, contact details and addresses it recognizes before any text is sent to an AI provider. In live mode, the remaining text is processed in the United States by third-party AI service providers under their API data-use terms; Batatis deletes its own stored case data and files after 7 days or on request.'
# The response header and the JSON meta notice are this same sentence.
PII_NOTICE = PRIVACY_NOTICE


def assistant_notice(provider: str) -> str:
    name = 'Anthropic' if provider == 'anthropic' else 'OpenAI'
    return (f'AI help explains information and administrative completeness; it does not determine technical correctness. '
            f'In live mode, your question, recent chat and selected application context (application facts and any selected case message) are sent to {name}, after the names, contact details and addresses Batatis recognizes are removed. '
            'Batatis does not store this assistant chat; stored applications and '
            'their messages are deleted after 7 days or when the application is deleted.')
