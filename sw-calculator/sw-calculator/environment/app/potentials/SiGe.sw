# Two-species test parameterisation in LAMMPS "sw" format.
# Synthetic values chosen so that every entry is distinguishable; not a physical fit.
# Two-body terms use entry (i,j,j); the three-body term centred on i uses
# lambda, epsilon, costheta0 of entry (i,j,k) and gamma, sigma, a of entries (i,j,j) and (i,k,k).
# element1 element2 element3 epsilon sigma a lambda gamma costheta0 A B p q tol
Si Si Si 2.1683 2.0951 1.80 21.0 1.20 -0.333333333333 7.049556277 0.6022245584 4.0 0.0 0.0
Ge Ge Ge 1.93   2.181  1.80 31.0 1.20 -0.333333333333 7.049556277 0.6022245584 4.0 0.0 0.0
Si Ge Ge 2.0491 2.1381 1.80 25.5 1.15 -0.333333333333 7.049556277 0.6022245584 4.0 0.0 0.0
Ge Si Si 2.0491 2.1381 1.80 27.0 1.25 -0.333333333333 7.049556277 0.6022245584 4.0 0.0 0.0
Si Si Ge 2.10   2.30   1.70 23.0 1.40 -0.30          6.50        0.70         4.2 0.1 0.0
Si Ge Si 2.10   2.30   1.70 23.0 1.40 -0.30          6.50        0.70         4.2 0.1 0.0
Ge Si Ge 1.99   2.25   1.75 29.0 1.10 -0.36          6.90        0.65         3.8 0.2 0.0
Ge Ge Si 1.99   2.25   1.75 29.0 1.10 -0.36          6.90        0.65         3.8 0.2 0.0
