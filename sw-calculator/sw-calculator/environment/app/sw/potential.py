"""Reader for LAMMPS-format Stillinger-Weber (.sw) parameter files."""

FIELDS = ("epsilon", "sigma", "a", "lambda", "gamma", "costheta0", "A", "B", "p", "q", "tol")


def read_sw(path):
    """Return the parameters of the first entry as {field: float}.

    TODO(multi-element): only single-element files are supported.
    """
    with open(path) as handle:
        for line in handle:
            words = line.split("#", 1)[0].split()
            if len(words) >= 14:
                return dict(zip(FIELDS, (float(w) for w in words[3:14])))
    raise ValueError(f"{path}: no complete entry on a single line")
