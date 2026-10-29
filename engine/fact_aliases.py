"""Latest logical answer, shared by normalization, policy and PDF filling."""
from .process_fields import PROCESS_ALIASES

ALIASES = {
    'owner_name': ('owner_name', 'owner', 'section_a.owner_name'),
    'owner_rep_name': ('owner_rep_name', 'representative', 'applicant_name'),
    'request_date': ('request_date', 'application_date', 'date', 'section_a.date'),
    'mailing_address': ('mailing_address', 'mailingAddress'),
    'municipal_address': ('municipal_address', 'municipalAddress', 'civic_address', 'address'),
    'legal_description': ('legal_description', 'legalDescription', 'section_b.legal_description'),
    'permit_number': ('permit_number', 'permit', 'section_b.permit_number'),
    'alternative_description': ('alternative_description', 'alternative'),
    'pathway': ('pathway', 'path'),
    'professional_name': ('professional_name', 'responsible_professional', 'professional.name'),
    'division_c_2_3_1': ('division_c_2_3_1', 'division_c_documentation', 'div_c_2_3_1'),
    'signature': ('signature', 'applicant_signature', 'section_a.signature'),
    'signature_date': ('signature_date', 'section_a.signature_date'),
    **{f'process.{key}': tuple(name for alias in names for name in (alias, f'process.{alias}'))
       for key, names in PROCESS_ALIASES.items()},
}
FIELD_KEYS = {alias: key for key, names in ALIASES.items() for alias in names}
LOGICAL_KEYS = {'owner_rep_name': 'representative', 'request_date': 'application_date',
                'municipal_address': 'civic_address',
                **{f'process.{key}': key for key in PROCESS_ALIASES}}


def latest(case):
    out = {}
    for fact in case.facts:
        out[FIELD_KEYS.get(fact.field, fact.field)] = fact
    return out


WITHDRAWN_REF = 'Answer withdrawn by applicant'


def is_withdrawal(fact) -> bool:
    """A cleared answer: the applicant removed it, so nothing is left to confirm."""
    return fact.source.ref == WITHDRAWN_REF or (fact.value == '' and fact.status == 'unconfirmed')
