"""Reader for LAMMPS-format Stillinger-Weber (.sw) parameter files."""

FIELDS = ("epsilon", "sigma", "a", "lambda", "gamma", "costheta0", "A", "B", "p", "q", "tol")


def read_sw(path):
    """Return {(e1, e2, e3): {field: float}} from a .sw file.

    Entries are 14 whitespace-separated fields and may span lines; text after
    '#' is a comment.
    """
    tokens = []
    with open(path) as handle:
        for line in handle:
            tokens.extend(line.split("#", 1)[0].split())
    if not tokens or len(tokens) % 14:
        raise ValueError(f"{path}: expected a multiple of 14 fields, got {len(tokens)}")
    table = {}
    for k in range(0, len(tokens), 14):
        key = tuple(tokens[k:k + 3])
        table[key] = dict(zip(FIELDS, (float(v) for v in tokens[k + 3:k + 14])))
    return table
