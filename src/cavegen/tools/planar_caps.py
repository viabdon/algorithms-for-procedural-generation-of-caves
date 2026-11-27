"""Geometry of finite planar polygons on a voxel lattice."""

import numpy as np
from matplotlib.path import Path as Polygon


def vertices_xyz(section):
    return section.point + section.polygon.vertices[:-1] @ section.uv_basis.T


def raster_cap_voxels(section, size, tolerance, shape_zyx=None):
    """Return ZYX voxel indices whose centres satisfy the plane and polygon tests."""
    vertices = vertices_xyz(section)
    half_width = size * np.abs(section.normal).sum() / 2 + tolerance
    margin = half_width + tolerance
    start = np.floor((vertices.min(axis=0) - margin)[::-1] / size).astype(int)
    stop = np.floor((vertices.max(axis=0) + margin)[::-1] / size).astype(int) + 1
    if shape_zyx is not None:
        start = np.maximum(start, 0)
        stop = np.minimum(stop, shape_zyx)
    if np.any(stop <= start):
        return np.empty((0, 3), dtype=int)
    # Bound temporary memory even when a large oblique polygon spans many slices.
    _, height, width = stop - start
    slab = max(1, 131072 // (int(height) * int(width)))
    found = []
    for z in range(start[0], stop[0], slab):
        depth = min(stop[0] - z, slab)
        indices = np.indices((depth, height, width)).reshape(3, -1).T + [z, *start[1:]]
        relative = (indices[:, ::-1] + .5) * size - section.point
        near = np.abs(relative @ section.normal) <= half_width
        inside = section.polygon.contains_points(relative[near] @ section.uv_basis, radius=tolerance)
        found.append(indices[near][inside])
    return np.concatenate(found)


def polygons_intersect(first, second, tolerance):
    """Test finite polygons in XYZ, including coplanar overlap."""
    a, b = vertices_xyz(first), vertices_xyz(second)
    if np.any((a.max(axis=0) < b.min(axis=0) - tolerance)
              | (b.max(axis=0) < a.min(axis=0) - tolerance)):
        return False
    relative = a - second.point
    distances = relative @ second.normal
    if np.all(np.abs(distances) <= tolerance):
        projected = np.vstack((relative, relative[0])) @ second.uv_basis
        return second.polygon.intersects_path(Polygon(projected, closed=True), filled=True)
    for vertices, plane in ((a, second), (b, first)):
        relative = vertices - plane.point
        ends = np.roll(relative, -1, axis=0)
        start_d, end_d = relative @ plane.normal, ends @ plane.normal
        touching = np.abs(start_d) <= tolerance
        crossing = ((start_d < -tolerance) & (end_d > tolerance)
                    | (start_d > tolerance) & (end_d < -tolerance))
        t = start_d[crossing] / (start_d[crossing] - end_d[crossing])
        crossings = relative[crossing] + t[:, None] * (ends[crossing] - relative[crossing])
        candidates = np.vstack((relative[touching], crossings))
        if plane.polygon.contains_points(candidates @ plane.uv_basis, radius=2 * tolerance).any():
            return True
    return False
