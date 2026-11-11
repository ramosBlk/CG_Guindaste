"""Recursos OpenGL e composicao/renderizacao da cena."""

import numpy as np
import pygame
from OpenGL.GL import (
    GL_BACK,
    GL_BLEND,
    GL_CLAMP_TO_BORDER,
    GL_COLOR_BUFFER_BIT,
    GL_CULL_FACE,
    GL_DEPTH_ATTACHMENT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_COMPONENT,
    GL_DEPTH_COMPONENT24,
    GL_DEPTH_TEST,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_COMPLETE,
    GL_LINEAR,
    GL_LINEAR_MIPMAP_LINEAR,
    GL_NEAREST,
    GL_NONE,
    GL_REPEAT,
    GL_RGBA,
    GL_RGBA8,
    GL_TEXTURE0,
    GL_TEXTURE1,
    GL_TEXTURE_2D,
    GL_TEXTURE_BORDER_COLOR,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRUE,
    GL_UNSIGNED_BYTE,
    GL_VERTEX_SHADER,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    glActiveTexture,
    glBindFramebuffer,
    glBindTexture,
    glBindVertexArray,
    glBlendFunc,
    glCheckFramebufferStatus,
    glClear,
    glClearColor,
    glCullFace,
    glDisable,
    glDrawBuffer,
    glEnable,
    glFramebufferTexture2D,
    glGenFramebuffers,
    glGenTextures,
    glGenerateMipmap,
    glGetUniformLocation,
    glReadBuffer,
    glTexImage2D,
    glTexParameterfv,
    glTexParameteri,
    glUniform1f,
    glUniform1i,
    glUniform3f,
    glUniformMatrix4fv,
    glUseProgram,
    glViewport,
)
from OpenGL.GL.shaders import compileProgram, compileShader

from .animation import TrainState
from .camera import Camera
from .crane import CraneController
from .crane_parts import CranePartsBuilder
from .geometry import make_cube, make_cylinder, make_sphere, make_track_geometry
from .hud import ControlsHud
from .math3d import (
    look_at,
    normalize,
    orthographic,
    perspective,
    scale_matrix,
    translation,
)
from .settings import (
    SHADOW_SIZE,
    TRACK_Z,
)
from .train_parts import TrainPartsBuilder
from .shaders import (
    DEPTH_FRAGMENT_SHADER,
    DEPTH_VERTEX_SHADER,
    FRAGMENT_SHADER,
    VERTEX_SHADER,
)


def set_matrix(program, uniform_name, matrix):
    glUniformMatrix4fv(
        glGetUniformLocation(program, uniform_name),
        1,
        GL_TRUE,
        np.asarray(matrix, dtype=np.float32),
    )


def create_train_texture():
    surface = pygame.Surface((128, 128), flags=pygame.SRCALPHA, depth=32)
    surface.fill((31, 83, 145, 255))
    pygame.draw.rect(surface, (238, 174, 48, 255), (0, 14, 128, 18))
    pygame.draw.rect(surface, (19, 46, 75, 255), (0, 96, 128, 32))
    for x in range(0, 128, 32):
        pygame.draw.rect(surface, (46, 109, 177, 255), (x, 42, 16, 45))
    image = pygame.image.tostring(surface, "RGBA", True)
    texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 128, 128, 0, GL_RGBA, GL_UNSIGNED_BYTE, image)
    glGenerateMipmap(GL_TEXTURE_2D)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glBindTexture(GL_TEXTURE_2D, 0)
    return texture


def make_shadow_target():
    framebuffer = glGenFramebuffers(1)
    depth_texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, depth_texture)
    glTexImage2D(
        GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24, SHADOW_SIZE, SHADOW_SIZE, 0,
        GL_DEPTH_COMPONENT, GL_FLOAT, None
    )
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER)
    glTexParameterfv(GL_TEXTURE_2D, GL_TEXTURE_BORDER_COLOR, (1.0, 1.0, 1.0, 1.0))
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, depth_texture, 0)
    glDrawBuffer(GL_NONE)
    glReadBuffer(GL_NONE)
    status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    if status != GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError(f"Framebuffer de shadow mapping invalido: 0x{status:x}")
    return framebuffer, depth_texture


class Scene:
    def __init__(self):
        self.cube, self.cylinder, self.sphere = make_cube(), make_cylinder(), make_sphere()
        self.train_parts_builder = TrainPartsBuilder(
            self.cube, self.cylinder, self.sphere
        )
        self.crane_parts_builder = CranePartsBuilder(self.cube, self.cylinder)
        self.program = compileProgram(
            compileShader(VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER),
        )
        self.depth_program = compileProgram(
            compileShader(DEPTH_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(DEPTH_FRAGMENT_SHADER, GL_FRAGMENT_SHADER),
        )
        self.train_texture = create_train_texture()
        self.shadow_fbo, self.shadow_texture = make_shadow_target()
        self.track_pieces = make_track_geometry()
        self.controls_hud = ControlsHud()
        self.train, self.camera, self.crane, self.paused = (
            TrainState(),
            Camera(),
            CraneController(),
            False,
        )
        self.light_direction = normalize((-0.45, -1.0, -0.35))
        light_eye = -self.light_direction * 24.0
        self.light_space = orthographic(-28, 28, -18, 18, 1, 70) @ look_at(
            light_eye, (0, 0, 5), (0, 1, 0)
        )
        self.ground_model = (
                translation(0, -0.20, TRACK_Z) @ scale_matrix(25.0, 0.18, 7.0)
        )
        self.platform_model = (
                translation(0, 0.10, TRACK_Z + 1.55) @ scale_matrix(2.65, 0.18, 0.72)
        )
        self.signal_pole_model = (
                translation(2.3, 1.20, TRACK_Z + 1.55) @ scale_matrix(0.10, 1.25, 0.10)
        )
        self.signal_head_model = (
                translation(2.3, 2.52, TRACK_Z + 1.55) @ scale_matrix(0.28, 0.38, 0.25)
        )

    def _draw(self, mesh, model, color, textured=False, emissive=0.0, alpha=1.0):
        glUniformMatrix4fv(glGetUniformLocation(self.program, "uModel"), 1, GL_TRUE, model)
        glUniform3f(glGetUniformLocation(self.program, "uBaseColor"), *color)
        glUniform1i(glGetUniformLocation(self.program, "uUseTexture"), int(textured))
        glUniform1f(glGetUniformLocation(self.program, "uEmissive"), emissive)
        glUniform1f(glGetUniformLocation(self.program, "uAlpha"), alpha)
        glUniform1f(glGetUniformLocation(self.program, "uShininess"), 36.0)
        if textured:
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.train_texture)
            glUniform1i(glGetUniformLocation(self.program, "uColorTexture"), 0)
        mesh.draw()

    def _draw_shadow(self, mesh, model):
        glUniformMatrix4fv(
            glGetUniformLocation(self.depth_program, "uModel"), 1, GL_TRUE, model
        )
        mesh.draw()

    def _scene_parts(self):
        parts = [(self.cube, self.ground_model, (0.32, 0.39, 0.30), False, 0.0)]
        parts.extend(
            (self.cube, model, color, False, 0.0) for model, color in self.track_pieces
        )
        parts.extend(
            (
                (self.cube, self.platform_model, (0.70, 0.66, 0.56), False, 0.0),
                (self.cube, self.signal_pole_model, (0.20, 0.22, 0.24), False, 0.0),
                (self.cube, self.signal_head_model, (0.20, 0.22, 0.24), False, 0.0),
            )
        )
        lamp_color = (0.20, 0.95, 0.35) if self.train.stopped else (1.0, 0.48, 0.08)
        lamp = (
                translation(2.3, 2.55, TRACK_Z + 1.26)
                @ scale_matrix(0.13, 0.14, 0.08)
        )
        parts.append((self.sphere, lamp, lamp_color, False, 0.75))
        parts.extend(self.crane_parts_builder.build(self.crane, self.train))
        parts.extend(self.train_parts_builder.build(self.train))
        return parts

    def _render_shadow_pass(self, parts):
        glViewport(0, 0, SHADOW_SIZE, SHADOW_SIZE)
        glBindFramebuffer(GL_FRAMEBUFFER, self.shadow_fbo)
        glClear(GL_DEPTH_BUFFER_BIT)
        glUseProgram(self.depth_program)
        set_matrix(self.depth_program, "uLightSpace", self.light_space)
        for mesh, model, _color, _textured, _emissive in parts:
            self._draw_shadow(mesh, model)

    def _render_scene_pass(self, parts, width, height):
        glViewport(0, 0, width, height)
        glClearColor(0.48, 0.70, 0.83, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glUseProgram(self.program)
        set_matrix(self.program, "uView", self.camera.view_matrix())
        set_matrix(
            self.program,
            "uProjection",
            perspective(48.0, width / max(height, 1), 0.1, 100.0),
        )
        set_matrix(self.program, "uLightSpace", self.light_space)
        glUniform3f(
            glGetUniformLocation(self.program, "uLightDirection"),
            *self.light_direction,
        )
        glUniform3f(
            glGetUniformLocation(self.program, "uCameraPosition"),
            *self.camera.position,
        )
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.shadow_texture)
        glUniform1i(glGetUniformLocation(self.program, "uShadowMap"), 1)
        for mesh, model, color, textured, emissive in parts:
            self._draw(mesh, model, color, textured, emissive)

    def _draw_aim_line(self):
        aim_line_height = 1.35
        aim_line = (
            translation(
                float(self.crane.hook_position[0]),
                aim_line_height,
                float(self.crane.hook_position[2]),
            )
            @ scale_matrix(0.035, aim_line_height, 0.035)
        )
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._draw(
            self.cube,
            aim_line,
            (1.0, 0.04, 0.04),
            emissive=0.65,
            alpha=0.2,
        )

    def render(self, width, height):
        parts = self._scene_parts()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)

        self._render_shadow_pass(parts)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        self._render_scene_pass(parts, width, height)
        self._draw_aim_line()
        glDisable(GL_BLEND)
        glBindTexture(GL_TEXTURE_2D, 0)
        glBindVertexArray(0)
        glUseProgram(0)
        self.controls_hud.draw(width, height, paused=self.paused)
