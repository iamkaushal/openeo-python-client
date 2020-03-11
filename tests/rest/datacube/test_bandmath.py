import pytest

import openeo
import openeo.internal.graphbuilder_040
from openeo.rest import BandMathException
from openeo.rest.connection import Connection
from ... import load_json_resource, get_download_graph

API_URL = "https://oeo.net"


def reset_graphbuilder():
    """Reset 0.4.0 style graph builder"""
    openeo.internal.graphbuilder_040.GraphBuilder.id_counter = {}


@pytest.fixture(params=["0.4.0", "1.0.0"])
def api_version(request):
    return request.param


def _setup_connection(api_version, requests_mock) -> Connection:
    # TODO: make this more reusable?
    requests_mock.get(API_URL + "/", json={"api_version": api_version})
    s2_properties = {
        "properties": {
            "cube:dimensions": {
                "bands": {"type": "bands", "values": ["B02", "B03", "B04", "B08"]}
            },
            "eo:bands": [
                {"name": "B02", "common_name": "blue", "center_wavelength": 0.4966},
                {"name": "B03", "common_name": "green", "center_wavelength": 0.560},
                {"name": "B04", "common_name": "red", "center_wavelength": 0.6645},
                {"name": "B08", "common_name": "nir", "center_wavelength": 0.8351},
            ]
        }
    }
    # Classic Sentinel2 collection
    requests_mock.get(API_URL + "/collections/SENTINEL2_RADIOMETRY_10M", json=s2_properties)
    # Alias for quick tests
    requests_mock.get(API_URL + "/collections/S2", json=s2_properties)
    # Some other collections
    requests_mock.get(API_URL + "/collections/MASK", json={})
    requests_mock.get(API_URL + "/collections/SENTINEL2_SCF", json={
        "properties": {
            "cube:dimensions": {
                "bands": {"type": "bands", "values": ["SCENECLASSIFICATION", "MASKFOO"]}
            },
            "eo:bands": [
                {"name": "SCENECLASSIFICATION"},
                {"name": "MASK"},
            ]
        }
    })
    return openeo.connect(API_URL)


@pytest.fixture
def connection(api_version, requests_mock) -> Connection:
    """Connection fixture to a backend of given version with some image collections."""
    reset_graphbuilder()
    openeo.internal.graphbuilder_040.GraphBuilder.id_counter = {}
    return _setup_connection(api_version, requests_mock)


@pytest.fixture
def con100(requests_mock) -> Connection:
    """Connection fixture to a 1.0.0 backend with some image collections."""
    return _setup_connection("1.0.0", requests_mock)


def test_band_basic(connection, api_version):
    cube = connection.load_collection("SENTINEL2_RADIOMETRY_10M")
    expected_graph = load_json_resource('data/%s/band0.json' % api_version)
    assert cube.band(0).graph == expected_graph
    reset_graphbuilder()
    assert cube.band("B02").graph == expected_graph
    # TODO graph contains "spectral_band" hardcoded


def test_indexing(connection, api_version):
    def check_cube(cube, band_index):
        reset_graphbuilder()
        assert cube.band(band_index).graph == expected_graph
        reset_graphbuilder()
        assert cube.band("B04").graph == expected_graph
        reset_graphbuilder()
        assert cube.band("red").graph == expected_graph

    cube = connection.load_collection("SENTINEL2_RADIOMETRY_10M")
    expected_graph = load_json_resource('data/%s/band_red.json' % api_version)
    check_cube(cube, 2)

    cube2 = cube.filter_bands(['red', 'green'])
    expected_graph = load_json_resource('data/%s/band_red_filtered.json' % api_version)
    check_cube(cube2, 0)


def test_evi(connection, api_version):
    cube = connection.load_collection("SENTINEL2_RADIOMETRY_10M")
    B02 = cube.band('B02')
    B04 = cube.band('B04')
    B08 = cube.band('B08')
    evi_cube = (2.5 * (B08 - B04)) / ((B08 + 6.0 * B04 - 7.5 * B02) + 1.0)
    actual_graph = get_download_graph(evi_cube)
    expected_graph = load_json_resource('data/%s/evi_graph.json' % api_version)
    assert actual_graph == expected_graph


def test_ndvi_udf(connection, api_version):
    s2_radio = connection.load_collection("SENTINEL2_RADIOMETRY_10M")
    ndvi_coverage = s2_radio.apply_tiles("def myfunction(tile):\n"
                                         "    print(tile)\n"
                                         "    return tile")
    actual_graph = get_download_graph(ndvi_coverage)
    expected_graph = load_json_resource('data/%s/udf_graph.json' % api_version)["process_graph"]
    assert actual_graph == expected_graph


def test_ndvi_udf_v100(con100):
    s2_radio = con100.load_collection("SENTINEL2_RADIOMETRY_10M")
    ndvi_coverage = s2_radio.reduce_bands_udf("def myfunction(tile):\n"
                                              "    print(tile)\n"
                                              "    return tile")
    actual_graph = get_download_graph(ndvi_coverage)
    expected_graph = load_json_resource('data/1.0.0/udf_graph.json')["process_graph"]
    assert actual_graph == expected_graph


@pytest.mark.parametrize(["process", "expected"], [
    ((lambda b: b + 3), {
        "add1": {"process_id": "add", "arguments": {"x": {"from_node": "arrayelement1"}, "y": 3}, "result": True}
    }),
    ((lambda b: 3 + b), {
        "add1": {"process_id": "add", "arguments": {"x": 3, "y": {"from_node": "arrayelement1"}}, "result": True}
    }),
    ((lambda b: 3 + b + 5), {
        "add1": {"process_id": "add", "arguments": {"x": 3, "y": {"from_node": "arrayelement1"}}},
        "add2": {"process_id": "add", "arguments": {"x": {"from_node": "add1"}, "y": 5}, "result": True}
    }
     ),
    ((lambda b: b - 3), {
        "subtract1": {"process_id": "subtract", "arguments": {"x": {"from_node": "arrayelement1"}, "y": 3},
                      "result": True}
    }),
    ((lambda b: 3 - b), {
        "subtract1": {"process_id": "subtract", "arguments": {"x": 3, "y": {"from_node": "arrayelement1"}},
                      "result": True}
    }),
    ((lambda b: 2 * b), {
        "multiply1": {"process_id": "multiply", "arguments": {"x": 2, "y": {"from_node": "arrayelement1"}},
                      "result": True}
    }),
    ((lambda b: b * 6), {
        "multiply1": {"process_id": "multiply", "arguments": {"x": {"from_node": "arrayelement1"}, "y": 6},
                      "result": True}
    }),
    ((lambda b: b / 8), {
        "divide1": {"process_id": "divide", "arguments": {"x": {"from_node": "arrayelement1"}, "y": 8}, "result": True}
    }),
])
def test_band_operation(con100, process, expected):
    s2 = con100.load_collection("S2")
    b = s2.band('B04')
    c = process(b)

    callback = {"arrayelement1": {
        "process_id": "array_element", "arguments": {"data": {"from_argument": "data"}, "index": 2}
    }}
    callback.update(expected)
    assert c.graph == {
        "loadcollection1": {
            "process_id": "load_collection",
            "arguments": {"id": "S2", "spatial_extent": None, "temporal_extent": None}
        },
        "reducedimension1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "loadcollection1"},
                "reducer": {"process_graph": callback},
                "dimension": "spectral_bands",
            },
            "result": True,
        }
    }


@pytest.mark.skip("TODO issue #107")
def test_merge_issue107(con100):
    """https://github.com/Open-EO/openeo-python-client/issues/107"""
    s2 = con100.load_collection("S2")
    a = s2.filter_bands(['B02'])
    b = s2.filter_bands(['B04'])
    c = a.merge(b)

    flat = c.graph
    # There should be only one `load_collection` node (but two `filter_band` ones)
    processes = sorted(n["process_id"] for n in flat.values())
    assert processes == ["filter_bands", "filter_bands", "merge_cubes", "load_collection"]


def test_reduce_dimension_binary(con100):
    s2 = con100.load_collection("S2")
    reducer = {
        "process_id": "add",
        "arguments": {"x": {"from_argument": "x"}, "y": {"from_argument": "y"}}
    }
    # TODO: use a public version of reduce_dimension_binary?
    x = s2._reduce(dimension="bands", reducer=reducer, process_id="reduce_dimension_binary")
    assert x.graph == {
        'loadcollection1': {
            'arguments': {'id': 'S2', 'spatial_extent': None, 'temporal_extent': None},
            'process_id': 'load_collection',
        },
        'reducedimensionbinary1': {
            'process_id': 'reduce_dimension_binary',
            'arguments': {
                'data': {'from_node': 'loadcollection1'},
                'dimension': 'bands',
                'reducer': {'process_graph': {
                    'add1': {
                        'process_id': 'add',
                        'arguments': {'x': {'from_argument': 'x'}, 'y': {'from_argument': 'y'}},
                        'result': True
                    }
                }}
            },
            'result': True
        }}


def test_invert_band(connection, api_version):
    cube = connection.load_collection("S2")
    band = cube.band('B04')
    result = (~band)
    assert result.graph == load_json_resource('data/%s/bm_invert_band.json' % api_version)


def test_eq_scalar(connection, api_version):
    cube = connection.load_collection("S2")
    band = cube.band('B04')
    result = (band == 42)
    assert result.graph == load_json_resource('data/%s/bm_eq_scalar.json' % api_version)


def test_gt_scalar(connection, api_version):
    cube = connection.load_collection("S2")
    band = cube.band('B04')
    result = (band > 42)
    assert result.graph == load_json_resource('data/%s/bm_gt_scalar.json' % api_version)


def test_add_sub_mul_div_scalar(connection, api_version):
    cube = connection.load_collection("S2")
    band = cube.band('B04')
    result = (((band + 42) - 10) * 3) / 2
    assert result.graph == load_json_resource('data/%s/bm_add_sub_mul_div_scalar.json' % api_version)


def test_add_bands(connection, api_version):
    cube = connection.load_collection("S2")
    b4 = cube.band("B04")
    b3 = cube.band("B03")
    result = b4 + b3
    assert result.graph == load_json_resource('data/%s/bm_add_bands.json' % api_version)


def test_add_bands_different_collection(connection, api_version):
    if api_version == "0.4.0":
        pytest.skip("0.4.0 generates invalid result")
    b4 = connection.load_collection("S2").band("B04")
    b3 = connection.load_collection("SENTINEL2_RADIOMETRY_10M").band("B02")
    with pytest.raises(BandMathException):
        # TODO #123 implement band math with bands of different collections
        b4 + b3


def test_logical_not_equal(connection, api_version):
    s2 = connection.load_collection("SENTINEL2_SCF")
    scf_band = s2.band("SCENECLASSIFICATION")
    mask = scf_band != 4
    actual = get_download_graph(mask)
    assert actual == load_json_resource('data/%s/notequal.json' % api_version)


def test_logical_or(connection, api_version):
    s2 = connection.load_collection("SENTINEL2_SCF")
    scf_band = s2.band("SCENECLASSIFICATION")
    mask = (scf_band == 2) | (scf_band == 5)
    actual = get_download_graph(mask)
    assert actual == load_json_resource('data/%s/logical_or.json' % api_version)


def test_logical_and(connection, api_version):
    s2 = connection.load_collection("SENTINEL2_SCF")
    b1 = s2.band("SCENECLASSIFICATION")
    b2 = s2.band("MASK")
    mask = (b1 == 2) & (b2 == 5)
    actual = get_download_graph(mask)
    assert actual == load_json_resource('data/%s/logical_and.json' % api_version)


def test_cube_merge_or(connection, api_version):
    s2 = connection.load_collection("S2")
    b1 = s2.band("B02") > 1
    b2 = s2.band("B03") > 2
    b1 = b1.linear_scale_range(0, 1, 0, 2)
    b2 = b2.linear_scale_range(0, 1, 0, 2)
    combined = b1 | b2
    actual = get_download_graph(combined)
    assert actual == load_json_resource('data/%s/cube_merge_or.json' % api_version)


def test_cube_merge_multiple(connection, api_version):
    if api_version == "0.4.0":
        pytest.skip("doesn't work in 0.4.0")
    s2 = connection.load_collection("S2")
    b1 = s2.band("B02")
    b1 = b1.linear_scale_range(0, 1, 0, 2)
    combined = b1 + b1 + b1
    actual = get_download_graph(combined)
    pytest.skip("#TODO #117: current implementation still does unnecessary (deep) copies of linearscalerange nodes")
    assert actual == load_json_resource('data/%s/cube_merge_multiple.json' % api_version)
