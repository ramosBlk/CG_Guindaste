"""Composicao das partes visuais do guindaste e das caixas."""

import numpy as np

from .math3d import (
    rotation_x,
    scale_matrix,
    segment_model,
    translation,
)
from .settings import (
    CRANE_X,
    CRANE_Z,
    CRATE_COLORS,
    CRATE_HALF_SIZE,
    CRATE_SOURCES,
)


class CranePartsBuilder:
    def __init__(self, cube, cylinder):
        self.cube = cube
        self.cylinder = cylinder

    def build(self, crane, train):
        parts = []

        def add(mesh, model, color, emissive=0.0):
            parts.append((mesh, model, color, False, emissive))

        chassis_color = (0.88, 0.55, 0.12)
        dark_metal = (0.16, 0.19, 0.21)
        add(
            self.cube,
            translation(CRANE_X, 0.52, CRANE_Z)
            @ scale_matrix(1.05, 0.20, 0.72),
            dark_metal,
        )
        add(
            self.cube,
            translation(CRANE_X, 0.78, CRANE_Z)
            @ scale_matrix(1.35, 0.12, 0.82),
            chassis_color,
        )
        add(
            self.cylinder,
            translation(CRANE_X + 0.12, 0.94, CRANE_Z)
            @ scale_matrix(0.48, 0.12, 0.48),
            (0.20, 0.23, 0.25),
        )
        add(
            self.cylinder,
            translation(CRANE_X + 0.12, 1.06, CRANE_Z)
            @ scale_matrix(0.24, 0.10, 0.24),
            (0.95, 0.68, 0.18),
        )
        add(
            self.cube,
            translation(CRANE_X - 0.62, 1.48, CRANE_Z)
            @ scale_matrix(0.43, 0.60, 0.55),
            chassis_color,
        )
        add(
            self.cube,
            translation(CRANE_X - 0.62, 1.52, CRANE_Z + 0.56)
            @ scale_matrix(0.29, 0.30, 0.025),
            (0.16, 0.53, 0.68),
        )
        add(
            self.cube,
            translation(CRANE_X - 0.62, 1.48, CRANE_Z - 0.56)
            @ scale_matrix(0.29, 0.30, 0.025),
            (0.16, 0.53, 0.68),
        )
        add(
            self.cube,
            translation(CRANE_X - 0.62, 2.10, CRANE_Z)
            @ scale_matrix(0.48, 0.08, 0.60),
            (0.17, 0.20, 0.22),
        )
        add(
            self.cube,
            translation(CRANE_X - 0.62, 1.96, CRANE_Z)
            @ scale_matrix(0.52, 0.045, 0.64),
            chassis_color,
        )
        for side in (-1, 1):
            for axle_x in (-0.78, 0.78):
                wheel = (
                    translation(CRANE_X + axle_x, 0.34, CRANE_Z + side * 0.72)
                    @ rotation_x(np.pi / 2)
                    @ scale_matrix(0.33, 0.16, 0.33)
                )
                add(self.cylinder, wheel, dark_metal)
                hub = (
                    translation(CRANE_X + axle_x, 0.34, CRANE_Z + side * 0.88)
                    @ rotation_x(np.pi / 2)
                    @ scale_matrix(0.13, 0.13, 0.035)
                )
                add(self.cylinder, hub, (0.91, 0.63, 0.18))

        for side in (-1, 1):
            add(
                self.cube,
                translation(CRANE_X, 0.60, CRANE_Z + side * 0.82)
                @ scale_matrix(1.32, 0.07, 0.06),
                (0.20, 0.23, 0.25),
            )
            for x in (-0.72, 0.72):
                add(
                    self.cube,
                    translation(CRANE_X + x, 0.69, CRANE_Z + side * 0.82)
                    @ scale_matrix(0.11, 0.035, 0.07),
                    (0.92, 0.68, 0.20),
                )

        hook_point = crane.hook_position
        attached = crane.has_crate
        for index, position in enumerate(CRATE_SOURCES):
            if index in train.loaded_crate_indices:
                continue
            if index == crane.active_crate and attached:
                continue
            if index in crane.dropped_crates:
                continue
            add(
                self.cube,
                translation(*position) @ scale_matrix(*CRATE_HALF_SIZE),
                CRATE_COLORS[index],
            )
        for index, position in crane.dropped_crates.items():
            add(
                self.cube,
                translation(*position) @ scale_matrix(*CRATE_HALF_SIZE),
                CRATE_COLORS[index],
            )
        if attached:
            add(
                self.cube,
                translation(*hook_point) @ scale_matrix(*CRATE_HALF_SIZE),
                CRATE_COLORS[crane.active_crate],
            )

        pivot = np.array((CRANE_X + 0.10, 2.15, CRANE_Z), dtype=np.float32)
        trolley = np.array(
            (hook_point[0], max(2.4, hook_point[1] + 0.88), hook_point[2]),
            dtype=np.float32,
        )
        add(self.cube, segment_model(pivot, trolley, 0.14), chassis_color)
        boom_offset = np.array((0.20, 0.0, 0.0), dtype=np.float32)
        for side in (-1, 1):
            rail_start = pivot + boom_offset * side
            rail_end = trolley + boom_offset * side
            add(
                self.cube,
                segment_model(rail_start, rail_end, 0.045),
                dark_metal,
            )
        for fraction in (0.35, 0.7):
            cross_center = pivot + (trolley - pivot) * fraction
            add(
                self.cube,
                segment_model(
                    cross_center - boom_offset,
                    cross_center + boom_offset,
                    0.035,
                ),
                (0.94, 0.70, 0.24),
            )
        add(
            self.cylinder,
            translation(*pivot)
            @ rotation_x(np.pi / 2)
            @ scale_matrix(0.23, 0.23, 0.16),
            dark_metal,
        )
        add(
            self.cube,
            translation(*trolley) @ scale_matrix(0.22, 0.13, 0.20),
            dark_metal,
        )
        cable_end = hook_point.copy()
        cable_end[1] += CRATE_HALF_SIZE[1] if attached else 0.10
        if trolley[1] - cable_end[1] > 0.08:
            add(
                self.cube,
                segment_model(trolley, cable_end, 0.035),
                dark_metal,
            )
        add(
            self.cube,
            translation(*cable_end) @ scale_matrix(0.12, 0.06, 0.12),
            chassis_color,
        )
        return parts
