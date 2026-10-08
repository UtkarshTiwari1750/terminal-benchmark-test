# Stillinger–Weber calculator contract

Units: eV, Å. Positions are Cartesian rows (`atoms.positions`), cell rows are lattice vectors.

## Parameter files

`/app/potentials/*.sw` use the LAMMPS `pair_style sw` file format. An entry is 14 whitespace-separated
fields, which may span several lines:

    element1 element2 element3 epsilon sigma a lambda gamma costheta0 A B p q tol

Text after `#` is a comment. `tol` is ignored. A file covering n elements has all n³ entries.

## Energy

Let the set of neighbours of atom i be every periodic image j′ = (atom j, lattice translation T) with
d_ij′ = r_j + T − r_i and r_ij′ = |d_ij′| < a_ij σ_ij, excluding only (j = i, T = 0). Translations
have zero components along non-periodic directions; along periodic directions all translations count,
so one atom can appear several times in a neighbour set, including images of i itself. Atoms may lie
outside the cell.

Two-body parameters ε_ij, σ_ij, a_ij, A_ij, B_ij, p_ij, q_ij, γ_ij come from entry (e_i, e_j, e_j).

    φ2(r) = A ε [B (σ/r)^p − (σ/r)^q] exp(σ / (r − aσ))

    φ3 = λ_ijk ε_ijk (cos θ_j′ik′ − cos θ0_ijk)²
         · exp(γ_ij σ_ij / (r_ij′ − a_ij σ_ij)) · exp(γ_ik σ_ik / (r_ik′ − a_ik σ_ik))

with λ_ijk, ε_ijk, cos θ0_ijk from entry (e_i, e_j, e_k) and cos θ_j′ik′ = d_ij′·d_ik′ / (r_ij′ r_ik′).

    E = ½ Σ_i Σ_{j′} φ2(r_ij′)  +  Σ_i Σ_{j′<k′} φ3(i, j′, k′)

where the last sum is over unordered pairs of distinct neighbour images of i. Terms vanish for
r ≥ aσ.

## Outputs

`StillingerWeber(path)` is an `ase.calculators.calculator.Calculator`.

- `get_potential_energy()`: E.
- `get_forces()`: F = −∂E/∂r, shape (N, 3).
- `get_stress()`: only for cells periodic in all three directions. ASE convention: σ = (1/V) ∂E/∂ε for a
  homogeneous strain ε applied to cell and positions, Voigt order xx, yy, zz, yz, xz, xy, eV/Å³.
- `calc.get_hessian(atoms)`: dense array of shape (3N, 3N), H[3a+α, 3b+β] = ∂²E / ∂r_aα ∂r_bβ in eV/Å²,
  where moving atom b moves all of its periodic images. Works for any `pbc`.

A calculator instance must give correct results when reused across different `Atoms` objects and after
positions, cell or species change.
