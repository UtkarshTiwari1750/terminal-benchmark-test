The flood-screening package in `/app/swe` solves the 2D shallow-water equations with bed topography, but still water over uneven beds starts to flow, depths go negative where shorelines move, and accuracy is first order. Make `swe.simulate` correct for wet, dry and partly flooded terrain. Final code must be in `/app/swe`, importable with `import swe` from `/app` using only installed packages.

## Equations and conventions

Unknowns are depth `h`, discharges `hu`, `hv`; bed elevation `z` is fixed in time; gravity `g`.

h_t + (hu)_x + (hv)_y = 0
(hu)_t + (hu²/h + g h²/2)_x + (huv)_y = −g h z_x
(hv)_t + (huv)_x + (hv²/h + g h²/2)_y = −g h z_y

Keep this signature:

`simulate(h, hu, hv, z, dx, dy, times, g=9.81, boundary="wall")`

- `h, hu, hv, z` are cell averages on a uniform grid, float arrays of shape `(ny, nx)`; axis 1 is `x` (spacing `dx`), axis 0 is `y` (spacing `dy`). `ny` or `nx` may be 1; a dimension of size 1 has no flow along it.
- `times` is a non-decreasing list of output times ≥ 0, starting from t = 0.
- Return a list with one `(h, hu, hv)` tuple per requested time, each array of the input shape, at exactly that time.
- `boundary` applies to all four sides: `"wall"` (reflective, no normal flow), `"periodic"`, or `"open"` (zero-gradient outflow).
- Initial depths are ≥ 0 and may be exactly 0.

## What is verified

Each call runs single-threaded in a fresh unprivileged process; only arrays pass in and out. References are analytic or invariants. "L1" means Σ|error|·dx (·dy in 2D). Every returned array must be finite and every depth must be ≥ 0 at every output.

1. **Still water stays still (20%).** Constant free surface over beds with emerged islands, submerged ridges, partly wet cells and dry shores, 1D (200 cells) and 2D (80×80), wall boundaries, outputs up to t = 2: every |hu|+|hv| ≤ 1e-11 and every depth within 1e-11 of its initial value.
2. **Dam breaks (20%).** Flat bed on [0,1], 400 cells, open boundaries, dam at x = 0.5, left depth 1, at rest, t = 0.1, compared with the exact Riemann solutions. Wet bed (right depth 0.1): L1 depth ≤ 2.5e-3, L1 discharge ≤ 6e-3. Dry bed (right depth 0), run once along x and once along y: L1 depth ≤ 2e-3, L1 discharge ≤ 4.5e-3, transverse discharge ≤ 1e-12.
3. **Second-order accuracy (20%).** Smooth periodic flow over a smooth bed, 1D, grids of 100, 200, 400, 800 and 1600 cells, t = 0.06. Differences between successive grids (fine solution averaged onto the coarse grid, L1 of h plus hu) must shrink with observed order ≥ 1.8 at every refinement; total mass equal across grids within 1e-12.
4. **Moving shorelines (25%).** Thacker's oscillating planar surface in a parabolic bowl (z = 0.5(r² − 1), amplitude parameter 0.5), wall boundaries on [−2,2]. 1D, 400 cells, at a quarter, half and full period: L1 depth ≤ 6e-4, L1 discharge ≤ 1e-3. 2D, 100×100, at a quarter and half period: L1 depth ≤ 5e-3, L1 discharge (both components) ≤ 9e-3, mirror symmetry in y within 1e-10. Relative mass error ≤ 1e-12 in both.
5. **Scale (15%).** The 2D bowl problem on a 256×256 grid to a quarter period must finish within 120 s of wall time, with L1 depth ≤ 1e-3 and relative mass error ≤ 1e-12.

Each call has a 300 s limit. Criteria are reported separately; full credit requires all five. `/app/examples` reproduces the complaints.
