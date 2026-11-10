"""Composicao das partes visuais do trem e dos vagoes."""

import math

from .animation import track_position
from .math3d import rotation_x, rotation_y, rotation_z, scale_matrix, translation
from .settings import (
    CARGO_WAGON_OFFSETS,
    CRATE_COLORS,
    CRATE_HALF_SIZE,
    WAGON_COLORS,
    WHEEL_RADIUS,
)


class TrainPartsBuilder:
    def __init__(self, cube, cylinder, sphere):
        self.cube = cube
        self.cylinder = cylinder
        self.sphere = sphere

    def build(self, train):
        position = track_position(train.lap_distance)
        root = translation(*position)
        wheel_rotation = train.wheel_distance / WHEEL_RADIUS
        parts = []

        def add(mesh, local, color, textured=False, emissive=0.0):
            parts.append((mesh, root @ local, color, textured, emissive))

        add(
            self.cube,
            translation(0, 0.54, 0) @ scale_matrix(1.12, 0.20, 0.53),
            (0.12, 0.15, 0.18),
        )
        add(
            self.cube,
            translation(0, 0.98, 0) @ scale_matrix(1.42, 0.45, 0.68),
            (1, 1, 1),
            True,
        )
        add(
            self.cube,
            translation(-0.15, 1.46, 0) @ scale_matrix(0.85, 0.12, 0.62),
            (0.16, 0.20, 0.24),
        )
        add(
            self.cube,
            translation(0, 0.69, 0) @ scale_matrix(1.50, 0.07, 0.72),
            (0.78, 0.50, 0.14),
        )
        for side in (-1, 1):
            add(
                self.cube,
                translation(-0.05, 0.92, side * 0.695)
                @ scale_matrix(1.12, 0.045, 0.025),
                (0.93, 0.65, 0.20),
            )
        add(
            self.cylinder,
            translation(0.62, 1.57, 0) @ scale_matrix(0.13, 0.26, 0.13),
            (0.13, 0.16, 0.18),
        )
        add(
            self.cylinder,
            translation(0.62, 1.80, 0) @ scale_matrix(0.19, 0.055, 0.19),
            (0.13, 0.16, 0.18),
        )
        for x in (-0.55, -0.05):
            add(
                self.sphere,
                translation(x, 1.48, 0) @ scale_matrix(0.12, 0.10, 0.12),
                (0.86, 0.61, 0.18),
            )

        for x in (-0.78, -0.18, 0.42):
            for side in (-1, 1):
                add(
                    self.cube,
                    translation(x, 1.18, side * 0.688)
                    @ scale_matrix(0.22, 0.20, 0.025),
                    (0.12, 0.52, 0.72),
                )
        add(
            self.cube,
            translation(1.435, 1.04, 0) @ scale_matrix(0.025, 0.26, 0.36),
            (0.60, 0.82, 0.90),
        )
        add(
            self.cube,
            translation(1.47, 0.69, 0) @ scale_matrix(0.13, 0.08, 0.58),
            (0.18, 0.20, 0.21),
        )
        for grille_z in (-0.38, -0.19, 0.0, 0.19, 0.38):
            add(
                self.cube,
                translation(1.51, 0.83, grille_z)
                @ scale_matrix(0.025, 0.14, 0.025),
                (0.72, 0.76, 0.78),
            )
        add(
            self.sphere,
            translation(1.49, 1.38, 0) @ scale_matrix(0.13, 0.13, 0.13),
            (1.0, 0.83, 0.40),
            emissive=0.65,
        )
        for side in (-1, 1):
            add(
                self.sphere,
                translation(1.48, 1.12, side * 0.43)
                @ scale_matrix(0.09, 0.09, 0.09),
                (1.0, 0.88, 0.55),
                emissive=0.22,
            )
            for x in (-0.82, 0.82):
                wheel_center_y = 0.60
                wheel_center_z = side * 0.59
                wheel = (
                    translation(x, wheel_center_y, wheel_center_z)
                    @ rotation_x(math.pi / 2)
                    @ rotation_y(wheel_rotation)
                    @ scale_matrix(WHEEL_RADIUS, 0.15, WHEEL_RADIUS)
                )
                add(self.cylinder, wheel, (0.12, 0.13, 0.14))
                wheel_frame = (
                    translation(x, wheel_center_y, wheel_center_z)
                    @ rotation_x(math.pi / 2)
                    @ rotation_y(wheel_rotation)
                )
                for spoke_index in range(4):
                    spoke_angle = spoke_index * math.pi / 2
                    spoke = (
                        wheel_frame
                        @ translation(
                            WHEEL_RADIUS * 0.48 * math.cos(spoke_angle),
                            WHEEL_RADIUS * 0.48 * math.sin(spoke_angle),
                            side * 0.153,
                        )
                        @ rotation_z(spoke_angle)
                        @ scale_matrix(WHEEL_RADIUS * 0.48, 0.025, 0.035)
                    )
                    add(self.cube, spoke, (0.76, 0.66, 0.38))
                hub = (
                    translation(x, wheel_center_y, side * 0.68)
                    @ rotation_x(math.pi / 2)
                    @ scale_matrix(0.10, 0.10, 0.025)
                )
                add(self.cylinder, hub, (0.72, 0.65, 0.40))

        for wagon_index, offset in enumerate(CARGO_WAGON_OFFSETS):
            wagon = root @ translation(offset, 0, 0)
            cargo_color = WAGON_COLORS[wagon_index]

            def add_cargo(mesh, local, color):
                parts.append((mesh, wagon @ local, color, False, 0.0))

            add_cargo(
                self.cube,
                translation(0, 0.55, 0) @ scale_matrix(1.12, 0.15, 0.55),
                (0.16, 0.18, 0.20),
            )
            for side in (-1, 1):
                add_cargo(
                    self.cube,
                    translation(0, 0.99, side * 0.49)
                    @ scale_matrix(1.05, 0.29, 0.06),
                    cargo_color,
                )
            for end in (-1, 1):
                add_cargo(
                    self.cube,
                    translation(end * 1.05, 0.99, 0)
                    @ scale_matrix(0.06, 0.29, 0.49),
                    cargo_color,
                )
            for side in (-1, 1):
                add_cargo(
                    self.cube,
                    translation(0, 1.30, side * 0.49)
                    @ scale_matrix(1.05, 0.16, 0.06),
                    cargo_color,
                )
            for end in (-1, 1):
                add_cargo(
                    self.cube,
                    translation(end * 1.05, 1.30, 0)
                    @ scale_matrix(0.06, 0.16, 0.49),
                    cargo_color,
                )
            if wagon_index < len(train.loaded_crate_indices):
                crate_index = train.loaded_crate_indices[wagon_index]
                add_cargo(
                    self.cube,
                    translation(0, 0.94, 0) @ scale_matrix(*CRATE_HALF_SIZE),
                    CRATE_COLORS[crate_index],
                )
            for side in (-1, 1):
                for axle_x in (-0.72, 0.72):
                    wheel_y = 0.37
                    wheel_z = side * 0.59
                    cargo_wheel = (
                        translation(axle_x, wheel_y, wheel_z)
                        @ rotation_x(math.pi / 2)
                        @ rotation_y(wheel_rotation)
                        @ scale_matrix(WHEEL_RADIUS, 0.15, WHEEL_RADIUS)
                    )
                    add_cargo(self.cylinder, cargo_wheel, (0.12, 0.13, 0.14))
                    wheel_face = (
                        translation(axle_x, wheel_y, side * 0.68)
                        @ rotation_x(math.pi / 2)
                        @ scale_matrix(0.10, 0.10, 0.025)
                    )
                    add_cargo(self.cylinder, wheel_face, (0.72, 0.65, 0.40))
        return parts
