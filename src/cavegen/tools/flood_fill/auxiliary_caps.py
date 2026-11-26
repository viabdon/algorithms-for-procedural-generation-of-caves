"""Propose synthetic patches from the exterior envelope of a measured barrier."""

import numpy as np
from scipy import ndimage as nd


def propose_auxiliary_caps(barrier, caps, seed, max_radius, protected_seeds=()):
    """Keep the synthetic envelope cells touching the enclosed seed component."""
    for radius in range(1, max_radius + 1):
        pad = radius + 2
        padded = np.pad(barrier, pad)
        expanded = nd.distance_transform_edt(~padded) <= radius
        closed = nd.distance_transform_edt(expanded) > radius
        solid = nd.binary_fill_holes(closed[(slice(pad, -pad),) * 3] | barrier)
        patch = solid & ~nd.binary_erosion(solid) & ~barrier
        if patch[seed] or not solid[seed]:
            continue
        labels, _ = nd.label(~(barrier | patch))
        interior = labels == labels[seed]
        if interior[0, 0, 0] or any(not interior[s] for s in protected_seeds):
            continue
        adjacent = nd.binary_dilation(interior)
        if not all((adjacent & cap).any() for cap in caps):
            continue
        # Removing cells away from the interior cannot open a path across its boundary.
        patch &= adjacent
        return patch, interior, radius
    return np.zeros_like(barrier), None, 0
