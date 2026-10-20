import json
from datetime import date

import pytest

from engine.ccmc import API_URL, CCMCRegistry, RegistryUnavailable


def record(number='13016-R', product='Example Continuous Exterior Insulation', manufacturer='Example Manufacturer'):
    return dict(ccmcno=number, organization_eng=manufacturer, organization_fre='Fabricant Éxemple',
                products_eng=json.dumps([product]), products_fre=None, status_eng='Active', ispublished='Y')


def registry(tmp_path, records=None, **kwargs):
    path = tmp_path / 'registry.json'
    path.write_text(json.dumps({'items': records or [record()], 'hasMore': False}))
    return CCMCRegistry(path, '2026-10-18', today=lambda: date(2026, 10, 20), **kwargs)


def test_live_product_manufacturer_and_date_cache(tmp_path):
    calls = []
    def fetch(url):
        calls.append(url)
        return {'items': [record()], 'hasMore': False}
    client = registry(tmp_path, fetch_json=fetch,
        fetch_text=lambda _: '<td>CCMC number:</td><td>13016-R</td><td>Modified date:</td><td>2025-10-21</td>')
    result = client.search('continuous exterior')
    assert result.source == 'live' and not result.cached
    assert result.results[0].date == '2025-10-21' and result.results[0].date_kind == 'modified'
    assert result.results[0].message.startswith('found an evaluation: 13016-R, Example Continuous')
    assert client.search('manufacturer').cached and client.search('fabricant exemple').total_matches == 1
    assert calls == [API_URL]
    assert 'complies' not in result.model_dump_json().lower()


def test_offline_negative_is_labelled_and_never_invents_dates(tmp_path):
    def offline(_):
        raise OSError('network down')
    client = registry(tmp_path, fetch_json=offline, fetch_text=lambda _: pytest.fail('offline must not fetch report'))
    found = client.search('Example')
    assert found.source == 'snapshot' and found.registry_date == '2026-10-18'
    assert found.results[0].date is None and 'date not available' in found.results[0].message
    missing = client.search('BTRboard')
    assert not missing.results and 'no evaluation found in the registry (searched 2026-10-20)' in missing.message
    assert 'Offline snapshot dated 2026-10-18' in missing.message


def test_pagination_is_complete_before_negative(tmp_path):
    pages = {API_URL: {'items': [record()], 'hasMore': True, 'links': [{'rel': 'next', 'href': '?offset=1'}]},
             API_URL + '?offset=1': {'items': [record('03240-L', 'Esgard')], 'hasMore': False}}
    client = registry(tmp_path, fetch_json=pages.__getitem__, fetch_text=lambda _: '')
    result = client.search('Esgard')
    assert result.source == 'live' and result.results[0].assessment_kind == 'listing'
    assert result.results[0].message.startswith('found a listing: 03240-L, Esgard,')
    assert 'found an evaluation' not in result.results[0].message
    assert result.results[0].date is None


@pytest.mark.parametrize('live', [
    {'items': [], 'hasMore': True},
    {'items': [record()], 'hasMore': True, 'links': [{'rel': 'next', 'href': 'https://untrusted.example/next'}]},
    {'items': [{'ccmcno': 'invented'}], 'hasMore': False},
    {'items': [record(), record()], 'hasMore': False},
])
def test_malformed_or_partial_live_data_uses_snapshot(tmp_path, live):
    client = registry(tmp_path, fetch_json=lambda _: live, fetch_text=lambda _: '')
    assert client.search('Example').source == 'snapshot'


def test_unavailable_snapshot_is_an_error_never_a_negative(tmp_path):
    client = CCMCRegistry(tmp_path / 'missing.json', offline=True)
    with pytest.raises(RegistryUnavailable):
        client.search('BTRboard')


def test_cache_expiry_and_unknown_custom_snapshot_date(tmp_path):
    tick = [0]
    calls = []
    def fetch(url):
        calls.append(url)
        return {'items': [record()], 'hasMore': False}
    client = registry(tmp_path, fetch_json=fetch, fetch_text=lambda _: '', clock=lambda: tick[0], ttl_seconds=10)
    assert not client.search('Example').cached
    tick[0] = 9
    assert client.search('Example').cached
    tick[0] = 11
    assert not client.search('Example').cached and len(calls) == 2
    other = CCMCRegistry(client.snapshot_path, offline=True)
    assert other.search('Example').registry_date == 'unknown'


@pytest.mark.parametrize('query', ['', '  ', '---', 'a' * 201])
def test_invalid_search_never_downloads(tmp_path, query):
    client = registry(tmp_path, fetch_json=lambda _: pytest.fail('invalid query must not fetch'))
    with pytest.raises(ValueError):
        client.search(query)


def test_an_unrelated_or_unavailable_report_does_not_supply_a_date(tmp_path):
    client = registry(tmp_path, fetch_json=lambda _: {'items': [record()], 'hasMore': False},
                      fetch_text=lambda _: '<p>CCMC number: 00000-R Modified date: 2026-10-20</p>')
    assert client.search('Example').results[0].date is None
