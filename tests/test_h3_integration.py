import pytest
h3=pytest.importorskip("h3",reason="real h3 package not installed in packaging environment")
from quakemesh_core.geo import H3GeoIndex

def test_real_h3_adapter_round_trip_operations():
    g=H3GeoIndex();c=g.cell(12.9716,77.5946,9);p=g.parent(c,7)
    assert h3.is_valid_cell(c) and h3.is_valid_cell(p)
    assert h3.get_resolution(c)==9 and h3.get_resolution(p)==7
    assert p in g.disk(p,1)
    assert g.grid_distance(p,p)==0
    boundary=g.boundary(p);assert len(boundary)>=5
