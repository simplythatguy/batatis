"""Privacy notice shown by the API and the web chrome.

The first sentence is the demo line. Stored cases stay until the applicant
deletes them; this app does not expire them on a timer. The processor line
names OpenAI (US). When live mode is on, the header also says that pasted
text and uploaded content are sent to OpenAI, and it points at OpenAI's own
API retention page. None of this is a finding that a design complies.
"""

PRIVACY_SENTENCE = 'Do not upload personal information. Demo data may be deleted.'
PROCESSOR_LINE = 'OpenAI (US) is a processor of text sent for a live model call.'
LIVE_SEND_LINE = 'Pasted text and uploaded content are sent to OpenAI (US) for processing.'
DONT_PASTE = "Don't paste personal information you don't need."
DELETE_LINE = 'Delete a stored case with DELETE /cases/{case_id}.'
OPENAI_RETENTION_URL = 'https://openai.com/policies/api-data-usage-policies'
# Checked 2026-10-20 against https://openai.com/policies/api-data-usage-policies
# (page updated January 8, 2026). Verbatim, under "How does OpenAI handle data
# retention and monitoring for API usage?":
# "Except for certain endpoints and features listed in our platform documentation, OpenAI may securely retain API inputs and outputs for up to 30 days to provide the services and to identify abuse. After 30 days, API inputs and outputs are removed from our systems, unless we are legally required to retain them."
OPENAI_RETENTION_LINE = (
    'OpenAI may securely retain API inputs and outputs for up to 30 days to provide the '
    'services and to identify abuse, except for certain endpoints and features listed in '
    f'its platform documentation, and unless the law requires longer retention. See {OPENAI_RETENTION_URL}'
)
PRIVACY_NOTICE = f'{PRIVACY_SENTENCE}\n{PROCESSOR_LINE}'
# Offline header. Header values are one line. The sidebar keeps each sentence on its own line.
PRIVACY_HEADER = f'{PRIVACY_SENTENCE} {PROCESSOR_LINE} {DONT_PASTE} {DELETE_LINE}'


def privacy_header(*, live: bool) -> str:
    """Notice for this response. The send-to-OpenAI lines appear only when live mode is on."""
    if not live:
        return PRIVACY_HEADER
    return (
        f'{PRIVACY_SENTENCE} {PROCESSOR_LINE} {LIVE_SEND_LINE} {DONT_PASTE} '
        f'{DELETE_LINE} {OPENAI_RETENTION_LINE}'
    )
