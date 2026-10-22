"""Array endpoints leave the wire as ``{items, meta}``. Other objects stay as they are."""


def listed(payload):
    if isinstance(payload, dict) and set(payload) == {'items', 'meta'} and isinstance(payload.get('items'), list):
        return payload['items']
    return payload
