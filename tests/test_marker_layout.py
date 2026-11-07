"""Marker label spacing is visual only; longitude data stays unchanged."""
import random
import pytest

from astrochart.domain import spread_marker_angles


def circular_gaps(angles):
    a = sorted(angles)
    return [a[i + 1] - a[i] for i in range(len(a) - 1)] + [a[0] + 360 - a[-1]]


@pytest.mark.parametrize("longitudes", [
    [10], [30, 31, 32, 33, 85, 115, 225],
    [359, 0, 1, 2, 100, 130, 250], [0] * 10,
    [5, 350, 0, 10, 15, 20, 25, 90, 180, 270],
    [i * 36 for i in range(10)],
])
def test_cluster_labels_do_not_overlap(longitudes):
    labels = spread_marker_angles(longitudes, min_gap=15)
    assert len(labels) == len(longitudes)
    assert all(0 <= x < 360 for x in labels)
    if len(labels) > 1:
        assert min(circular_gaps(labels)) >= 15 - 1e-8


def test_no_displacement_if_already_clear():
    original = [i * 36 for i in range(10)]
    labels = spread_marker_angles(original, 15)
    assert labels == pytest.approx(original)


def test_many_random_clusters_avoid_seam_collisions():
    rng = random.Random(7)
    for _ in range(100):
        original = [rng.uniform(0, 360) for _ in range(10)]
        labels = spread_marker_angles(original, 15)
        assert min(circular_gaps(labels)) >= 15 - 1e-8
