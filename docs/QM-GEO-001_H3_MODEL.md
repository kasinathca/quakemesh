# QM-GEO-001 — H3 Spatial Model

## 1. Why H3

The project needs a canonical cloud spatial identity that is coarser than raw GPS coordinates, supports neighborhood operations, and can represent geographic diversity consistently. H3 provides hierarchical hexagonal indexing and grid-neighborhood functions.

## 2. Two resolutions

- `h3_device_resolution = 9`: canonical cell associated with an individual device observation.
- `h3_correlation_resolution = 7`: parent cell used for diversity, spatial clustering, targeting and event footprint.

These are prototype defaults, not scientifically optimized seismic parameters.

## 3. Canonicalization

```text
latitude/longitude (in transit)
          │
          ▼
   H3 resolution 9 cell
          │ parent
          ▼
   H3 resolution 7 cell
          │
          ├─ persisted evidence/device state
          └─ correlation identity
```

The application tables intentionally do not have latitude/longitude columns/attributes.

## 4. Detection Footprint

`Detection Footprint = unique correlation cells that supplied the evidence component satisfying confirmation.`

The footprint means “where corroborating QuakeMesh evidence came from.” It must not be described as an epicentre polygon.

## 5. Warning Frontier

For each footprint cell, compute `grid_disk(cell, warning_ring_k)`, union all results, then subtract the footprint.

```text
Warning Frontier = union(neighbourhoods) − Detection Footprint
```

Default `warning_ring_k=1` is an experiment parameter. The frontier is a notification-targeting construct, not a physical seismic wavefront and not a prediction of arrival time.

## 6. Spatial coherence

Evidence correlation first creates connected components in coarse-cell space using configured maximum H3 grid distance. This avoids meeting thresholds by combining geographically unrelated triggers that happened at similar times.

## 7. Test-only synthetic adapter

`SyntheticGeoIndex` exists only so pure algorithm tests can execute when `h3` cannot be installed in the packaging environment. Production/local runtime defaults to `H3GeoIndex` and raises an error if the real package is absent. Never publish synthetic cell strings as H3 output.
