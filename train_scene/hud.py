"""HUD de controles desenhado sobre a cena OpenGL.

Elementos:
- painel de controles com keycaps (recolhível com a tecla H);
- dica "[H] Controles" quando o painel está recolhido;
- aviso "PAUSADO" no topo central.

Cada elemento é desenhado pelo pygame em uma textura RGBA com o dobro da
resolução (supersampling 2x) e reduzida pela GPU com filtro linear, o que
suaviza texto, setas e cantos arredondados.

Integração com o restante do programa:
- ao pressionar H, chamar ``hud.toggle()``;
- a cada quadro, chamar ``hud.draw(largura, altura, paused=pausado)``.
O tempo do fade e do recolhimento automático é medido pelo próprio HUD
(``pygame.time.get_ticks``), então continua correndo durante a pausa.
"""

import ctypes
import math

import pygame
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_CULL_FACE,
    GL_DEPTH_TEST,
    GL_DYNAMIC_DRAW,
    GL_FLOAT,
    GL_FALSE,
    GL_FRAGMENT_SHADER,
    GL_LINEAR,
    GL_RGBA,
    GL_RGBA8,
    GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_UNSIGNED_BYTE,
    GL_VERTEX_SHADER,
    glActiveTexture,
    glBindBuffer,
    glBindTexture,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glDisable,
    glDrawArrays,
    glEnable,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenTextures,
    glGenVertexArrays,
    glGetUniformLocation,
    glTexImage2D,
    glTexParameteri,
    glUniform1f,
    glUniform1i,
    glUseProgram,
    glVertexAttribPointer,
)
from OpenGL.GL.shaders import compileProgram, compileShader


HUD_VERTEX_SHADER = """#version 330 core
layout(location = 0) in vec2 aPosition;
layout(location = 1) in vec2 aTexCoord;
out vec2 vTexCoord;
void main() {
    vTexCoord = aTexCoord;
    gl_Position = vec4(aPosition, 0.0, 1.0);
}
"""

HUD_FRAGMENT_SHADER = """#version 330 core
in vec2 vTexCoord;
uniform sampler2D uPanel;
uniform float uAlpha;
out vec4 fragColor;
void main() {
    vec4 color = texture(uPanel, vTexCoord);
    fragColor = vec4(color.rgb, color.a * uAlpha);
}
"""


# --------------------------------------------------------------------------
# Aparência (medidas em pixels lógicos; o desenho usa SUPERSAMPLE x)
# --------------------------------------------------------------------------
SUPERSAMPLE = 2
FONT_NAMES = "segoeui,arial,helvetica,dejavusans,liberationsans"

PANEL_WIDTH = 259
PANEL_HEIGHT = 248
PANEL_RADIUS = 10
PANEL_BORDER_WIDTH = 2
PADDING = 14

PANEL_BG = (12, 21, 31, 140)
PANEL_BORDER = (107, 177, 197, 255)
SEPARATOR_COLOR = (107, 177, 197, 170)
TITLE_COLOR = (255, 255, 255)
DESCRIPTION_COLOR = (241, 246, 249)
PAUSE_COLOR = (255, 255, 255)
SHADOW_ALPHA = 170

TITLE_CENTER_Y = 20
SEPARATOR_Y = 36
ROWS_TOP = 44
ROW_HEIGHT = 24

KEY_EDGE_COLOR = (4, 4, 6)
KEY_FACE_COLOR = (36, 38, 42)
KEY_OUTLINE_COLOR = (74, 80, 88)
KEY_LEGEND_COLOR = (214, 217, 222)
KEY_HEIGHT = 20
KEY_EDGE_HEIGHT = 3
KEY_RADIUS = 3
KEY_GAP = 6
DESCRIPTION_GAP = 10
KEY_WIDTH_SINGLE = 24
KEY_WIDTH_MEDIUM = 34
KEY_WIDTH_SPACE = 62

ARROWS = ("left", "right", "up", "down")

# (teclas, descrição), por ordem de importância.
CONTROLS = (
    (("left", "right"), "Girar lança"),
    (("up", "down"), "Estender / recolher"),
    (("Espaço",), "Pegar / soltar caixa"),
    (("1-5",), "Trocar câmera"),
    (("P",), "Pausar / retomar"),
    (("H",), "Mostrar / ocultar HUD"),
    (("F11",), "Tela cheia"),
    (("Esc",), "Sair"),
)


# --------------------------------------------------------------------------
# Desenho com pygame (superfícies RGBA)
# --------------------------------------------------------------------------
def _s(value):
    """Converte pixels lógicos em pixels da superfície supersampleada."""
    return int(round(value * SUPERSAMPLE))


def _font(size, bold=False):
    return pygame.font.SysFont(FONT_NAMES, _s(size), bold=bold)


def _new_surface(width, height):
    return pygame.Surface((_s(width), _s(height)), pygame.SRCALPHA, 32)


def _rect(surface, color, x, y, width, height, radius, border=0):
    pygame.draw.rect(
        surface,
        color,
        (_s(x), _s(y), _s(width), _s(height)),
        width=_s(border),
        border_radius=_s(radius),
    )


def _draw_text(surface, font, text, color, x, center_y, anchor="left", shadow=True):
    """Desenha texto com sombra sutil; devolve a largura lógica do texto."""
    image = font.render(text, True, color)
    left = _s(x) if anchor == "left" else round(_s(x) - image.get_width() / 2)
    top = round(_s(center_y) - image.get_height() / 2)
    if shadow:
        shadow_image = font.render(text, True, (0, 0, 0))
        shadow_image.set_alpha(SHADOW_ALPHA)
        surface.blit(shadow_image, (left + SUPERSAMPLE, top + SUPERSAMPLE))
    surface.blit(image, (left, top))
    return image.get_width() / SUPERSAMPLE


def _draw_arrow(surface, direction, center_x, center_y, color):
    half_length, half_width = 3.5, 4.5
    if direction == "left":
        points = [(center_x + half_length, center_y - half_width),
                  (center_x + half_length, center_y + half_width),
                  (center_x - half_length, center_y)]
    elif direction == "right":
        points = [(center_x - half_length, center_y - half_width),
                  (center_x - half_length, center_y + half_width),
                  (center_x + half_length, center_y)]
    elif direction == "up":
        points = [(center_x - half_width, center_y + half_length),
                  (center_x + half_width, center_y + half_length),
                  (center_x, center_y - half_length)]
    else:
        points = [(center_x - half_width, center_y - half_length),
                  (center_x + half_width, center_y - half_length),
                  (center_x, center_y + half_length)]
    pygame.draw.polygon(surface, color, [(_s(px), _s(py)) for px, py in points])


def _key_width(label):
    if label == "Espaço":
        return KEY_WIDTH_SPACE
    if label in ARROWS or len(label) == 1:
        return KEY_WIDTH_SINGLE
    return KEY_WIDTH_MEDIUM


def _draw_keycap(surface, label, x, y, key_font):
    """Keycap preta com relevo: face mais clara em cima, borda escura embaixo."""
    width = _key_width(label)
    face_height = KEY_HEIGHT - KEY_EDGE_HEIGHT
    _rect(surface, KEY_EDGE_COLOR, x, y, width, KEY_HEIGHT, KEY_RADIUS)
    _rect(surface, KEY_FACE_COLOR, x, y, width, face_height, KEY_RADIUS)
    _rect(surface, KEY_OUTLINE_COLOR, x, y, width, KEY_HEIGHT, KEY_RADIUS, border=1)
    center_x, center_y = x + width / 2, y + face_height / 2
    if label in ARROWS:
        _draw_arrow(surface, label, center_x, center_y, KEY_LEGEND_COLOR)
    else:
        _draw_text(surface, key_font, label, KEY_LEGEND_COLOR, center_x, center_y,
                   anchor="center", shadow=False)
    return width


def build_panel_surface():
    surface = _new_surface(PANEL_WIDTH, PANEL_HEIGHT)
    _rect(surface, PANEL_BG, 0, 0, PANEL_WIDTH, PANEL_HEIGHT, PANEL_RADIUS)
    _rect(surface, PANEL_BORDER, 0, 0, PANEL_WIDTH, PANEL_HEIGHT, PANEL_RADIUS,
          border=PANEL_BORDER_WIDTH)

    title_font = _font(18, bold=True)
    description_font = _font(16)
    key_font = _font(13, bold=True)

    _draw_text(surface, title_font, "CONTROLES", TITLE_COLOR, PADDING, TITLE_CENTER_Y)
    pygame.draw.line(
        surface,
        SEPARATOR_COLOR,
        (_s(PADDING), _s(SEPARATOR_Y)),
        (_s(PANEL_WIDTH - PADDING), _s(SEPARATOR_Y)),
        _s(1),
    )

    for index, (keys, description) in enumerate(CONTROLS):
        center_y = ROWS_TOP + index * ROW_HEIGHT + ROW_HEIGHT / 2
        x = PADDING
        for key in keys:
            x += _draw_keycap(surface, key, x, center_y - KEY_HEIGHT / 2, key_font)
            x += KEY_GAP
        x += DESCRIPTION_GAP - KEY_GAP
        _draw_text(surface, description_font, description, DESCRIPTION_COLOR, x, center_y)
    return surface


def build_hint_surface():
    """Dica do estado recolhido: keycap [H] + "Controles", sem fundo."""
    key_font = _font(13, bold=True)
    font = _font(16)
    text_width = font.size("Controles")[0] / SUPERSAMPLE
    gap = 8
    width = math.ceil(KEY_WIDTH_SINGLE + gap + text_width + 3)
    height = KEY_HEIGHT + 3
    surface = _new_surface(width, height)
    _draw_keycap(surface, "H", 0, 0, key_font)
    _draw_text(surface, font, "Controles", DESCRIPTION_COLOR,
               KEY_WIDTH_SINGLE + gap, KEY_HEIGHT / 2)
    return surface


def build_pause_surface():
    """Aviso "PAUSADO": só texto com sombra."""
    font = _font(24, bold=True)
    text_width, text_height = font.size("PAUSADO")
    width = math.ceil(text_width / SUPERSAMPLE) + 4
    height = math.ceil(text_height / SUPERSAMPLE) + 4
    surface = _new_surface(width, height)
    _draw_text(surface, font, "PAUSADO", PAUSE_COLOR, width / 2, height / 2,
               anchor="center")
    return surface


# --------------------------------------------------------------------------
# OpenGL
# --------------------------------------------------------------------------
class _Sprite:
    """Textura RGBA de um elemento do HUD, com tamanho lógico em pixels."""

    def __init__(self, surface):
        self.width = surface.get_width() // SUPERSAMPLE
        self.height = surface.get_height() // SUPERSAMPLE
        self.texture = glGenTextures(1)
        image = pygame.image.tostring(surface, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA8,
            surface.get_width(),
            surface.get_height(),
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            image,
        )
        glBindTexture(GL_TEXTURE_2D, 0)


class ControlsHud:
    WIDTH = PANEL_WIDTH
    HEIGHT = PANEL_HEIGHT
    MARGIN = 16
    FADE_SECONDS = 0.2
    AUTO_COLLAPSE_SECONDS = 5.0
    HINT_OPACITY = 0.6

    def __init__(self):
        self.program = compileProgram(
            compileShader(HUD_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(HUD_FRAGMENT_SHADER, GL_FRAGMENT_SHADER),
        )
        self._panel_location = glGetUniformLocation(self.program, "uPanel")
        self._alpha_location = glGetUniformLocation(self.program, "uAlpha")
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self._configure_vertex_buffer()

        self.panel = _Sprite(build_panel_surface())
        self.hint = _Sprite(build_hint_surface())
        self.pause = _Sprite(build_pause_surface())

        # Começa expandido e recolhe sozinho depois de alguns segundos.
        self.expanded = True
        self._panel_alpha = 1.0
        self._auto_collapse_left = self.AUTO_COLLAPSE_SECONDS
        self._last_ticks = pygame.time.get_ticks()

    def _configure_vertex_buffer(self):
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)
        stride = 4 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(
            1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(2 * 4)
        )
        glBindVertexArray(0)

    def toggle(self):
        """Expande ou recolhe o painel (tecla H)."""
        self.expanded = not self.expanded
        self._auto_collapse_left = (
            self.AUTO_COLLAPSE_SECONDS if self.expanded else 0.0
        )
        self._last_ticks = pygame.time.get_ticks()

    def _advance(self):
        now = pygame.time.get_ticks()
        dt = min((now - self._last_ticks) / 1000.0, 0.1)
        self._last_ticks = now

        if self.expanded and self._auto_collapse_left > 0.0:
            self._auto_collapse_left -= dt
            if self._auto_collapse_left <= 0.0:
                self._auto_collapse_left = 0.0
                self.expanded = False

        target = 1.0 if self.expanded else 0.0
        step = dt / self.FADE_SECONDS
        if self._panel_alpha < target:
            self._panel_alpha = min(target, self._panel_alpha + step)
        else:
            self._panel_alpha = max(target, self._panel_alpha - step)

    def _draw_sprite(self, sprite, left, top, alpha, screen_width, screen_height):
        right, bottom = left + sprite.width, top + sprite.height
        x_left = 2.0 * left / screen_width - 1.0
        x_right = 2.0 * right / screen_width - 1.0
        y_top = 1.0 - 2.0 * top / screen_height
        y_bottom = 1.0 - 2.0 * bottom / screen_height
        vertices = (
            (x_left, y_bottom, 0.0, 0.0),
            (x_right, y_bottom, 1.0, 0.0),
            (x_right, y_top, 1.0, 1.0),
            (x_left, y_bottom, 0.0, 0.0),
            (x_right, y_top, 1.0, 1.0),
            (x_left, y_top, 0.0, 1.0),
        )
        glUniform1f(self._alpha_location, alpha)
        glBindTexture(GL_TEXTURE_2D, sprite.texture)
        glBufferData(
            GL_ARRAY_BUFFER,
            len(vertices) * 4 * 4,
            (ctypes.c_float * (len(vertices) * 4))(
                *(coordinate for vertex in vertices for coordinate in vertex)
            ),
            GL_DYNAMIC_DRAW,
        )
        glDrawArrays(GL_TRIANGLES, 0, 6)

    def draw(self, screen_width, screen_height, paused=False):
        if screen_width <= 0 or screen_height <= 0:
            return
        self._advance()

        panel_alpha = self._panel_alpha
        hint_alpha = self.HINT_OPACITY * (1.0 - panel_alpha)

        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glUseProgram(self.program)
        glUniform1i(self._panel_location, 0)
        glActiveTexture(GL_TEXTURE0)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)

        # Painel e dica ocupam o mesmo canto; durante o fade fazem crossfade.
        if hint_alpha > 0.001:
            self._draw_sprite(self.hint, self.MARGIN, self.MARGIN, hint_alpha,
                              screen_width, screen_height)
        if panel_alpha > 0.001:
            self._draw_sprite(self.panel, self.MARGIN, self.MARGIN, panel_alpha,
                              screen_width, screen_height)
        if paused:
            self._draw_sprite(self.pause, (screen_width - self.pause.width) // 2,
                              self.MARGIN, 1.0, screen_width, screen_height)

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)