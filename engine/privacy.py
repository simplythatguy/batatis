"""Privacy notice shown by the API and the web chrome.

The first sentence is the demo retention line. The second names the processor
for live model calls. Neither sentence is a finding that a design complies.
"""

PRIVACY_SENTENCE = 'Do not upload personal information. Demo data may be deleted.'
PROCESSOR_LINE = 'OpenAI (US) is a processor of text sent for a live model call.'
PRIVACY_NOTICE = f'{PRIVACY_SENTENCE}\n{PROCESSOR_LINE}'
# Header values are one line. The sidebar keeps the processor on its own line.
PRIVACY_HEADER = f'{PRIVACY_SENTENCE} {PROCESSOR_LINE}'
