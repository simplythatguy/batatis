"""Human label and display string for a fact. `field` and `value` stay the machine form."""
from __future__ import annotations

_LABELS = {
    'professional.part4_design': 'Designed under Part 4',
    'part4_design': 'Designed under Part 4',
    'professional.occupancy': 'Building type',
    'occupancy': 'Building type',
    'building.occupancy': 'Building type',
    'building.type': 'Building type',
    'professional.storeys': 'Storeys',
    'building.storeys': 'Storeys',
    'storeys': 'Storeys',
    'professional.building_area_m2': 'Building area',
    'building_area_m2': 'Building area',
    'building.area': 'Building area',
    'professional.principal_dwelling_units': 'Principal dwelling units',
    'principal_dwelling_units': 'Principal dwelling units',
    'professional.farm_public_use': 'Farm building for public use',
    'farm_public_use': 'Farm building for public use',
    'professional.preserved_wood_foundation_part4': 'Preserved wood foundation under Part 4',
    'preserved_wood_foundation_part4': 'Preserved wood foundation under Part 4',
    'professional.roof_trusses': 'Wood roof trusses',
    'roof_trusses': 'Wood roof trusses',
    'professional.prescriptive_route_confirmed': 'Prescriptive design route',
    'prescriptive_route_confirmed': 'Prescriptive design route',
    'professional.ahj_requires_professional': 'Authority requires a professional',
    'ahj_requires_professional': 'Authority requires a professional',
    'professional.special_safety_concerns': 'Size or complexity requires a professional',
    'special_safety_concerns': 'Size or complexity requires a professional',
    'professional.professional_judgement_required': 'Reserved professional judgement',
    'professional_judgement_required': 'Reserved professional judgement',
    'professional.professional_scope_resolved': 'Professional-law scope resolved',
    'professional_scope_resolved': 'Professional-law scope resolved',
    'professional.fire_suppression': 'Fire suppression system',
    'fire_suppression': 'Fire suppression system',
    'professional.fire_alarm': 'Fire alarm system',
    'fire_alarm': 'Fire alarm system',
    'building.height': 'Building height',
    'building.sprinklered': 'Sprinklered',
    'assembly.material': 'Wall assembly',
    'site.limiting_distance': 'Limiting distance',
    'egress.window': 'Bedroom egress window',
    'project.description': 'Description',
    'alternative': 'Proposed alternative',
    'ccmc_evaluation': 'CCMC evaluation',
    'evidence.letter': 'Letter',
    'scope': 'Jurisdiction-wide',
    'applicant.role': 'Role',
    'applicant_type': 'Role',
    'role': 'Role',
}

_BOOL_FIELDS = {
    'professional.part4_design', 'part4_design',
    'professional.farm_public_use', 'farm_public_use',
    'professional.preserved_wood_foundation_part4', 'preserved_wood_foundation_part4',
    'professional.roof_trusses', 'roof_trusses',
    'professional.prescriptive_route_confirmed', 'prescriptive_route_confirmed',
    'professional.ahj_requires_professional', 'ahj_requires_professional',
    'professional.special_safety_concerns', 'special_safety_concerns',
    'professional.professional_judgement_required', 'professional_judgement_required',
    'professional.professional_scope_resolved', 'professional_scope_resolved',
    'professional.fire_suppression', 'fire_suppression',
    'professional.fire_alarm', 'fire_alarm',
    'building.sprinklered',
    'ccmc_evaluation',
}

_VALUES = {
    'single_family': 'Single-family dwelling',
    'multi_family': 'Multi-family dwelling',
    'hotel': 'Hotel',
    'assembly': 'Assembly occupancy',
    'care': 'Care occupancy',
    'treatment': 'Treatment occupancy',
    'detention': 'Detention occupancy',
    'business': 'Business occupancy',
    'mercantile': 'Mercantile occupancy',
    'industrial': 'Industrial occupancy',
    'farm': 'Farm building',
    'relocatable_industrial_camp': 'Relocatable industrial camp',
    'mixed': 'Mixed use',
    'other': 'Other occupancy',
}


def fact_label(field: str) -> str:
    """Words for a fact field. The raw field stays on `field`."""
    if field in _LABELS:
        return _LABELS[field]
    tail = (field or '').split('.')[-1].replace('_', ' ').strip()
    if not tail:
        return field
    return tail[:1].upper() + tail[1:]


def display_value(field: str, value) -> str:
    """Words for a fact value. The raw value stays on `value`."""
    if value is None or value == '':
        return 'Not answered'
    if isinstance(value, bool) or field in _BOOL_FIELDS:
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        token = str(value).strip().casefold()
        if token in ('true', 'yes', '1'):
            return 'Yes'
        if token in ('false', 'no', '0'):
            return 'No'
    if isinstance(value, str) and value in _VALUES:
        return _VALUES[value]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def fact_display(field: str, value) -> str:
    """The line a person can read, for example 'Designed under Part 4: No'."""
    return f'{fact_label(field)}: {display_value(field, value)}'
