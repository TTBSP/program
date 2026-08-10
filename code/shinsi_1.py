import ast
import math
import pyglet
from pyglet import shapes
from pyglet.window import key, mouse
import pymunk

# ============================================================
# Inverted Pendulum Lab
# Python + Pyglet 2.1.x + Pymunk 7.x
# Verified against pyglet 2.1 Label(weight=...) and Line(thickness=...) APIs
# ============================================================

# -----------------------
# Simulation parameters
# -----------------------
WIDTH = 1280
HEIGHT = 720
PANEL_X = 880
SIM_W = PANEL_X

PPM = 220.0                 # pixels per meter
G = 9.81                    # m/s^2
PHYSICS_DT = 1.0 / 240.0    # fixed physics step
MAX_STEPS_PER_FRAME = 12

CART_MASS = 2.0             # kg
CART_W_M = 0.62             # m
CART_H_M = 0.20             # m
ROD_MASS = 0.35             # kg
ROD_LENGTH_M = 1.00         # m
ROD_RADIUS_M = 0.022        # m

CART_W = CART_W_M * PPM
CART_H = CART_H_M * PPM
ROD_LENGTH = ROD_LENGTH_M * PPM
ROD_RADIUS = ROD_RADIUS_M * PPM

TRACK_Y = 210
TRACK_LEFT = 80
TRACK_RIGHT = 820
START_ANGLE_DEG = 5.0

MANUAL_FORCE_N = 35.0
MAX_MOTOR_FORCE_N = 90.0
DISTURB_IMPULSE_NS = 0.22

DEFAULT_FORMULA = "-90*theta - 18*omega - 4*x - 8*v"

# -----------------------
# Theme
# -----------------------
C_BG = (12, 15, 22)
C_PANEL = (19, 23, 33)
C_CARD = (25, 31, 43)
C_CARD_2 = (31, 38, 52)
C_BORDER = (52, 62, 80)
C_TEXT = (231, 236, 244, 255)
C_MUTED = (145, 155, 174, 255)
C_ACCENT = (86, 156, 255)
C_ACCENT_2 = (76, 219, 181)
C_WARN = (255, 180, 76)
C_BAD = (255, 98, 108)
C_RAIL = (80, 91, 110)
C_CART = (71, 133, 219)
C_ROD = (237, 240, 247)
C_WHEEL = (45, 52, 65)
C_GRID = (37, 44, 58)

# ============================================================
# Safe formula evaluator
# ============================================================

ALLOWED_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "abs": abs,
    "min": min,
    "max": max,
    "pi": math.pi,
}


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def sign(value):
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


ALLOWED_FUNCS["clamp"] = clamp
ALLOWED_FUNCS["sign"] = sign

ALLOWED_VARIABLES = {
    "theta", "theta_deg", "omega", "x", "v", "t", "dt",
    "g", "M", "m", "L", "Fmax"
}


class FormulaValidator(ast.NodeVisitor):
    BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
    UNARY_OPS = (ast.UAdd, ast.USub, ast.Not)
    CMP_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
    BOOL_OPS = (ast.And, ast.Or)

    def visit_Expression(self, node):
        self.visit(node.body)

    def visit_BinOp(self, node):
        if not isinstance(node.op, self.BIN_OPS):
            raise ValueError("使えない演算子です")
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOp(self, node):
        if not isinstance(node.op, self.UNARY_OPS):
            raise ValueError("使えない単項演算子です")
        self.visit(node.operand)

    def visit_Constant(self, node):
        if not isinstance(node.value, (int, float, bool)):
            raise ValueError("数値以外の定数は使えません")

    def visit_Name(self, node):
        if node.id not in ALLOWED_VARIABLES and node.id not in ALLOWED_FUNCS:
            raise ValueError(f"未登録の名前: {node.id}")

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ValueError("関数の呼び方が不正です")
        if node.func.id not in ALLOWED_FUNCS or node.func.id == "pi":
            raise ValueError(f"使えない関数: {node.func.id}")
        if node.keywords:
            raise ValueError("キーワード引数は使えません")
        for arg in node.args:
            self.visit(arg)

    def visit_IfExp(self, node):
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_Compare(self, node):
        self.visit(node.left)
        for op in node.ops:
            if not isinstance(op, self.CMP_OPS):
                raise ValueError("使えない比較演算子です")
        for comp in node.comparators:
            self.visit(comp)

    def visit_BoolOp(self, node):
        if not isinstance(node.op, self.BOOL_OPS):
            raise ValueError("使えない論理演算子です")
        for value in node.values:
            self.visit(value)

    def generic_visit(self, node):
        raise ValueError(f"使えない構文: {type(node).__name__}")


def compile_formula(text):
    tree = ast.parse(text, mode="eval")
    FormulaValidator().visit(tree)
    return compile(tree, "<motor-formula>", "eval")


# ============================================================
# Small UI helpers
# ============================================================

class Button:
    def __init__(self, x, y, w, h, text, accent=False):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.accent = accent
        self.rect = shapes.Rectangle(x, y, w, h, color=C_ACCENT if accent else C_CARD_2, batch=ui_batch)
        self.label = pyglet.text.Label(
            text, x=x + w / 2, y=y + h / 2,
            anchor_x="center", anchor_y="center",
            font_size=11, weight="bold", color=C_TEXT, batch=text_batch
        )

    def hit(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

    def set_text(self, text):
        self.label.text = text

    def set_active(self, active):
        self.rect.color = C_ACCENT if active else C_CARD_2


# ============================================================
# Window / batches
# ============================================================

window = pyglet.window.Window(WIDTH, HEIGHT, "Inverted Pendulum Lab", resizable=False, vsync=True)

bg_batch = pyglet.graphics.Batch()
sim_batch = pyglet.graphics.Batch()
ui_batch = pyglet.graphics.Batch()
chart_batch = pyglet.graphics.Batch()
text_batch = pyglet.graphics.Batch()

# Background and panel
shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=C_BG, batch=bg_batch)
shapes.Rectangle(PANEL_X, 0, WIDTH - PANEL_X, HEIGHT, color=C_PANEL, batch=bg_batch)
shapes.Line(PANEL_X, 0, PANEL_X, HEIGHT, thickness=1, color=C_BORDER, batch=bg_batch)

# ============================================================
# Physics
# ============================================================

space = pymunk.Space()
space.gravity = (0, -G * PPM)
space.iterations = 30
space.damping = 1.0

cart_moment = pymunk.moment_for_box(CART_MASS, (CART_W, CART_H))
cart_body = pymunk.Body(CART_MASS, cart_moment)
cart_shape = pymunk.Poly.create_box(cart_body, (CART_W, CART_H))
cart_shape.filter = pymunk.ShapeFilter(group=1)

rod_moment = pymunk.moment_for_segment(
    ROD_MASS,
    (0, -ROD_LENGTH / 2),
    (0, ROD_LENGTH / 2),
    ROD_RADIUS,
)
rod_body = pymunk.Body(ROD_MASS, rod_moment)
rod_shape = pymunk.Segment(
    rod_body,
    (0, -ROD_LENGTH / 2),
    (0, ROD_LENGTH / 2),
    ROD_RADIUS,
)
rod_shape.filter = pymunk.ShapeFilter(group=1)

space.add(cart_body, cart_shape, rod_body, rod_shape)

# Cart center is constrained to this horizontal groove.
groove = pymunk.GrooveJoint(
    space.static_body,
    cart_body,
    (TRACK_LEFT + CART_W / 2, TRACK_Y),
    (TRACK_RIGHT - CART_W / 2, TRACK_Y),
    (0, 0),
)
rotation_lock = pymunk.RotaryLimitJoint(space.static_body, cart_body, 0, 0)

# Pendulum pivot: cart top <-> rod bottom.
pivot = pymunk.PivotJoint(
    cart_body,
    rod_body,
    (0, CART_H / 2),
    (0, -ROD_LENGTH / 2),
)

space.add(groove, rotation_lock, pivot)

# ============================================================
# Simulation drawing
# ============================================================

# Grid
for gx in range(80, 841, 55):
    shapes.Line(gx, 95, gx, 625, thickness=1, color=C_GRID, batch=sim_batch)
for gy in range(100, 626, 55):
    shapes.Line(60, gy, 850, gy, thickness=1, color=C_GRID, batch=sim_batch)

# Track and end stops
shapes.Line(TRACK_LEFT, TRACK_Y - CART_H / 2 - 18, TRACK_RIGHT, TRACK_Y - CART_H / 2 - 18,
            thickness=5, color=C_RAIL, batch=sim_batch)
shapes.Line(TRACK_LEFT, TRACK_Y - CART_H / 2 - 32, TRACK_RIGHT, TRACK_Y - CART_H / 2 - 32,
            thickness=2, color=(51, 59, 73), batch=sim_batch)
shapes.Rectangle(TRACK_LEFT - 5, TRACK_Y - CART_H / 2 - 42, 10, 50, color=C_RAIL, batch=sim_batch)
shapes.Rectangle(TRACK_RIGHT - 5, TRACK_Y - CART_H / 2 - 42, 10, 50, color=C_RAIL, batch=sim_batch)

# Zero marker
shapes.Line((TRACK_LEFT + TRACK_RIGHT) / 2, 115, (TRACK_LEFT + TRACK_RIGHT) / 2, 145,
            thickness=2, color=C_ACCENT, batch=sim_batch)

cart_draw = shapes.Rectangle(0, 0, CART_W, CART_H, color=C_CART, batch=sim_batch)
wheel_l = shapes.Circle(0, 0, 15, color=C_WHEEL, batch=sim_batch)
wheel_r = shapes.Circle(0, 0, 15, color=C_WHEEL, batch=sim_batch)
wheel_l_hub = shapes.Circle(0, 0, 5, color=C_ACCENT_2, batch=sim_batch)
wheel_r_hub = shapes.Circle(0, 0, 5, color=C_ACCENT_2, batch=sim_batch)
rod_draw = shapes.Line(0, 0, 0, 0, thickness=10, color=C_ROD, batch=sim_batch)
pivot_draw = shapes.Circle(0, 0, 9, color=C_ACCENT_2, batch=sim_batch)
com_draw = shapes.Circle(0, 0, 5, color=C_WARN, batch=sim_batch)
force_line = shapes.Line(0, 0, 0, 0, thickness=5, color=C_ACCENT, batch=sim_batch)
force_tip_a = shapes.Line(0, 0, 0, 0, thickness=4, color=C_ACCENT, batch=sim_batch)
force_tip_b = shapes.Line(0, 0, 0, 0, thickness=4, color=C_ACCENT, batch=sim_batch)

# Top-left labels
pyglet.text.Label("INVERTED PENDULUM LAB", x=36, y=682, font_size=18, weight="bold",
                  color=C_TEXT, batch=text_batch)
status_label = pyglet.text.Label("PAUSED", x=38, y=650, font_size=11, weight="bold",
                                 color=C_WARN + (255,) if len(C_WARN) == 3 else C_WARN, batch=text_batch)
help_label = pyglet.text.Label("MANUAL: ← / →     SPACE: run/pause     R: reset",
                               x=36, y=28, font_size=10, color=C_MUTED, batch=text_batch)

# ============================================================
# Right panel UI
# ============================================================

pyglet.text.Label("CONTROL", x=PANEL_X + 26, y=682, font_size=16, weight="bold",
                  color=C_TEXT, batch=text_batch)

manual_btn = Button(PANEL_X + 24, 626, 168, 38, "MANUAL", accent=True)
formula_btn = Button(PANEL_X + 208, 626, 168, 38, "FORMULA")

run_btn = Button(PANEL_X + 24, 574, 110, 36, "RUN", accent=True)
reset_btn = Button(PANEL_X + 145, 574, 110, 36, "RESET")
disturb_btn = Button(PANEL_X + 266, 574, 110, 36, "DISTURB")

# Formula card
shapes.Rectangle(PANEL_X + 24, 454, 352, 104, color=C_CARD, batch=ui_batch)
pyglet.text.Label("MOTOR FORMULA  →  force [N]", x=PANEL_X + 38, y=536,
                  font_size=10, weight="bold", color=C_MUTED, batch=text_batch)
formula_box = shapes.Rectangle(PANEL_X + 37, 486, 326, 36, color=C_CARD_2, batch=ui_batch)
formula_label = pyglet.text.Label(DEFAULT_FORMULA, x=PANEL_X + 48, y=504,
                                  anchor_y="center", font_name="Consolas", font_size=10,
                                  color=C_TEXT, batch=text_batch)
formula_state_label = pyglet.text.Label("Enterで適用", x=PANEL_X + 38, y=467,
                                        font_size=9, color=C_MUTED, batch=text_batch)

# Variable guide
shapes.Rectangle(PANEL_X + 24, 376, 352, 62, color=C_CARD, batch=ui_batch)
pyglet.text.Label("theta  omega  x  v  t", x=PANEL_X + 38, y=416,
                  font_name="Consolas", font_size=10, weight="bold", color=C_ACCENT_2 + (255,), batch=text_batch)
pyglet.text.Label("rad     rad/s    m    m/s   s     |  theta_deg / g / M / m / L / Fmax",
                  x=PANEL_X + 38, y=394, font_name="Consolas", font_size=8,
                  color=C_MUTED, batch=text_batch)

# Telemetry cards
telemetry_cards = [
    (PANEL_X + 24, 315, 168, 48, "ANGLE"),
    (PANEL_X + 208, 315, 168, 48, "ANG.VEL"),
    (PANEL_X + 24, 255, 168, 48, "CART X"),
    (PANEL_X + 208, 255, 168, 48, "CART V"),
]
telemetry_labels = []
for x0, y0, w0, h0, title in telemetry_cards:
    shapes.Rectangle(x0, y0, w0, h0, color=C_CARD, batch=ui_batch)
    pyglet.text.Label(title, x=x0 + 12, y=y0 + h0 - 16, font_size=8,
                      color=C_MUTED, batch=text_batch)
    lab = pyglet.text.Label("0.000", x=x0 + 12, y=y0 + 11, font_size=13, weight="bold",
                            color=C_TEXT, batch=text_batch)
    telemetry_labels.append(lab)

# Force indicator
shapes.Rectangle(PANEL_X + 24, 196, 352, 44, color=C_CARD, batch=ui_batch)
pyglet.text.Label("MOTOR", x=PANEL_X + 38, y=222, font_size=8, color=C_MUTED, batch=text_batch)
force_value_label = pyglet.text.Label("0.0 N", x=PANEL_X + 350, y=222, anchor_x="right",
                                      font_size=9, weight="bold", color=C_TEXT, batch=text_batch)
force_bar_bg = shapes.Rectangle(PANEL_X + 38, 207, 312, 7, color=C_CARD_2, batch=ui_batch)
force_bar = shapes.Rectangle(PANEL_X + 194, 207, 0, 7, color=C_ACCENT, batch=ui_batch)
force_center = shapes.Rectangle(PANEL_X + 193, 204, 2, 13, color=C_MUTED[:3], batch=ui_batch)

# Angle chart
chart_x = PANEL_X + 24
chart_y = 32
chart_w = 352
chart_h = 146
shapes.Rectangle(chart_x, chart_y, chart_w, chart_h, color=C_CARD, batch=ui_batch)
pyglet.text.Label("ANGLE HISTORY  ±45°", x=chart_x + 14, y=chart_y + chart_h - 18,
                  font_size=8, color=C_MUTED, batch=text_batch)
chart_mid_y = chart_y + 62
shapes.Line(chart_x + 14, chart_mid_y, chart_x + chart_w - 14, chart_mid_y,
            thickness=1, color=C_BORDER, batch=chart_batch)
for frac in (0.25, 0.75):
    yy = chart_y + 18 + (chart_h - 50) * frac
    shapes.Line(chart_x + 14, yy, chart_x + chart_w - 14, yy,
                thickness=1, color=C_GRID, batch=chart_batch)

HISTORY_N = 120
history = [0.0] * HISTORY_N
history_lines = []
plot_left = chart_x + 14
plot_right = chart_x + chart_w - 14
plot_bottom = chart_y + 18
plot_top = chart_y + chart_h - 34
for i in range(HISTORY_N - 1):
    line = shapes.Line(plot_left, chart_mid_y, plot_left, chart_mid_y,
                       thickness=2, color=C_ACCENT_2, batch=chart_batch)
    history_lines.append(line)

# ============================================================
# Runtime state
# ============================================================

mode = "manual"
running = False
left_down = False
right_down = False
formula_focused = False
formula_text = DEFAULT_FORMULA
formula_cursor = len(DEFAULT_FORMULA)
formula_select_all = False
formula_view_start = 0
formula_code = None
formula_error = ""
sim_time = 0.0
accumulator = 0.0
last_motor_force_n = 0.0
history_timer = 0.0


def apply_formula():
    global formula_code, formula_error
    try:
        formula_code = compile_formula(formula_text)
        formula_error = ""
        formula_state_label.text = "✓ formula active"
        formula_state_label.color = C_ACCENT_2 + (255,)
    except Exception as exc:
        formula_code = None
        formula_error = str(exc)
        formula_state_label.text = "ERROR: " + formula_error[:42]
        formula_state_label.color = C_BAD + (255,)


def reset_simulation():
    global running, sim_time, accumulator, last_motor_force_n, history, history_timer

    running = False
    sim_time = 0.0
    accumulator = 0.0
    last_motor_force_n = 0.0
    history_timer = 0.0
    history = [0.0] * HISTORY_N

    cart_x = (TRACK_LEFT + TRACK_RIGHT) / 2
    cart_body.position = (cart_x, TRACK_Y)
    cart_body.velocity = (0, 0)
    cart_body.angle = 0.0
    cart_body.angular_velocity = 0.0
    cart_body.force = (0, 0)
    cart_body.torque = 0.0

    angle = math.radians(START_ANGLE_DEG)
    pivot_world_x = cart_x
    pivot_world_y = TRACK_Y + CART_H / 2
    offset_x = -math.sin(angle) * (ROD_LENGTH / 2)
    offset_y = math.cos(angle) * (ROD_LENGTH / 2)

    rod_body.position = (pivot_world_x + offset_x, pivot_world_y + offset_y)
    rod_body.velocity = (0, 0)
    rod_body.angle = angle
    rod_body.angular_velocity = 0.0
    rod_body.force = (0, 0)
    rod_body.torque = 0.0

    cart_body.activate()
    rod_body.activate()
    run_btn.set_text("RUN")
    status_label.text = "PAUSED"
    status_label.color = C_WARN + (255,)
    refresh_visuals()


def get_state():
    center_x = (TRACK_LEFT + TRACK_RIGHT) / 2
    theta = rod_body.angle
    # Normalize only for display/control variables, keeping upright at 0.
    theta = (theta + math.pi) % (2 * math.pi) - math.pi
    omega = rod_body.angular_velocity
    x_m = (cart_body.position.x - center_x) / PPM
    v_mps = cart_body.velocity.x / PPM
    return theta, omega, x_m, v_mps


def evaluate_motor_force():
    if mode == "manual":
        if left_down and not right_down:
            return -MANUAL_FORCE_N
        if right_down and not left_down:
            return MANUAL_FORCE_N
        return 0.0

    if formula_code is None:
        return 0.0

    theta, omega, x_m, v_mps = get_state()
    env = {
        **ALLOWED_FUNCS,
        "theta": theta,
        "theta_deg": math.degrees(theta),
        "omega": omega,
        "x": x_m,
        "v": v_mps,
        "t": sim_time,
        "dt": PHYSICS_DT,
        "g": G,
        "M": CART_MASS,
        "m": ROD_MASS,
        "L": ROD_LENGTH_M,
        "Fmax": MAX_MOTOR_FORCE_N,
    }

    try:
        value = float(eval(formula_code, {"__builtins__": {}}, env))
        if not math.isfinite(value):
            return 0.0
        return clamp(value, -MAX_MOTOR_FORCE_N, MAX_MOTOR_FORCE_N)
    except Exception as exc:
        formula_state_label.text = "RUNTIME ERROR: " + str(exc)[:34]
        formula_state_label.color = C_BAD + (255,)
        return 0.0


def physics_step():
    global sim_time, last_motor_force_n

    force_n = evaluate_motor_force()
    last_motor_force_n = force_n

    # Convert N to Pymunk pixel-units: 1 m == PPM pixels.
    cart_body.apply_force_at_local_point((force_n * PPM, 0), (0, 0))

    space.step(PHYSICS_DT)
    sim_time += PHYSICS_DT


def disturb():
    # Repeatable sideways impulse at the rod COM.
    rod_body.apply_impulse_at_local_point((DISTURB_IMPULSE_NS * PPM, 0), (0, ROD_LENGTH / 3))
    rod_body.activate()


def update_history(dt):
    global history_timer, history
    if not running:
        return
    history_timer += dt
    if history_timer >= 1.0 / 30.0:
        history_timer = 0.0
        theta, _, _, _ = get_state()
        history = history[1:] + [math.degrees(theta)]


def refresh_history_lines():
    span = 45.0
    h = plot_top - plot_bottom
    for i, line in enumerate(history_lines):
        x1 = plot_left + (plot_right - plot_left) * i / (HISTORY_N - 1)
        x2 = plot_left + (plot_right - plot_left) * (i + 1) / (HISTORY_N - 1)
        d1 = clamp(history[i], -span, span)
        d2 = clamp(history[i + 1], -span, span)
        y1 = plot_bottom + h * (d1 + span) / (2 * span)
        y2 = plot_bottom + h * (d2 + span) / (2 * span)
        line.x, line.y, line.x2, line.y2 = x1, y1, x2, y2


def refresh_formula_display():
    global formula_view_start

    # Single-line editor view with a movable cursor and horizontal scrolling.
    max_chars = 39
    cursor_pos = max(0, min(formula_cursor, len(formula_text)))

    if formula_select_all and formula_focused:
        formula_view_start = 0
        raw = "[" + formula_text + "]"
        if len(raw) > max_chars:
            raw = raw[:max_chars - 1] + "…"
        formula_label.text = raw
    else:
        # Keep the cursor visible by showing a window around it.
        start = max(0, cursor_pos - max_chars + 1)
        end = min(len(formula_text), start + max_chars)
        if end - start < max_chars:
            start = max(0, end - max_chars)
        formula_view_start = start

        shown = formula_text[start:end]
        local_cursor = cursor_pos - start
        if formula_focused:
            shown = shown[:local_cursor] + "|" + shown[local_cursor:]

        if start > 0 and shown:
            shown = "…" + shown[1:]
        if end < len(formula_text) and shown:
            shown = shown[:-1] + "…"

        formula_label.text = shown

    formula_box.color = C_ACCENT if formula_focused else C_CARD_2


def refresh_visuals():
    # Cart
    cx, cy = cart_body.position
    cart_draw.x = cx - CART_W / 2
    cart_draw.y = cy - CART_H / 2

    wheel_y = cy - CART_H / 2 - 4
    wheel_l.x = cx - CART_W * 0.31
    wheel_l.y = wheel_y
    wheel_r.x = cx + CART_W * 0.31
    wheel_r.y = wheel_y
    wheel_l_hub.x, wheel_l_hub.y = wheel_l.x, wheel_l.y
    wheel_r_hub.x, wheel_r_hub.y = wheel_r.x, wheel_r.y

    # Rod endpoints from body local coordinates.
    p0 = rod_body.local_to_world((0, -ROD_LENGTH / 2))
    p1 = rod_body.local_to_world((0, ROD_LENGTH / 2))
    rod_draw.x, rod_draw.y, rod_draw.x2, rod_draw.y2 = p0.x, p0.y, p1.x, p1.y
    pivot_draw.x, pivot_draw.y = p0.x, p0.y
    com_draw.x, com_draw.y = rod_body.position.x, rod_body.position.y

    # Force arrow
    force_scale = 1.45
    fpx = clamp(last_motor_force_n * force_scale, -120, 120)
    ay = cy + CART_H / 2 + 28
    ax0 = cx
    ax1 = cx + fpx
    force_line.x, force_line.y, force_line.x2, force_line.y2 = ax0, ay, ax1, ay
    if abs(fpx) > 2:
        s = 1 if fpx > 0 else -1
        force_tip_a.x, force_tip_a.y = ax1, ay
        force_tip_a.x2, force_tip_a.y2 = ax1 - 10 * s, ay + 7
        force_tip_b.x, force_tip_b.y = ax1, ay
        force_tip_b.x2, force_tip_b.y2 = ax1 - 10 * s, ay - 7
    else:
        force_tip_a.x = force_tip_a.x2 = ax1
        force_tip_a.y = force_tip_a.y2 = ay
        force_tip_b.x = force_tip_b.x2 = ax1
        force_tip_b.y = force_tip_b.y2 = ay

    # Telemetry
    theta, omega, x_m, v_mps = get_state()
    telemetry_labels[0].text = f"{math.degrees(theta):+.2f}°"
    telemetry_labels[1].text = f"{omega:+.3f} rad/s"
    telemetry_labels[2].text = f"{x_m:+.3f} m"
    telemetry_labels[3].text = f"{v_mps:+.3f} m/s"

    force_value_label.text = f"{last_motor_force_n:+.1f} N"
    normalized = clamp(last_motor_force_n / MAX_MOTOR_FORCE_N, -1, 1)
    half = 156
    if normalized >= 0:
        force_bar.x = PANEL_X + 194
        force_bar.width = half * normalized
    else:
        force_bar.x = PANEL_X + 194 + half * normalized
        force_bar.width = -half * normalized

    refresh_formula_display()
    refresh_history_lines()


def update(dt):
    global accumulator
    if running:
        accumulator += min(dt, 0.05)
        steps = 0
        while accumulator >= PHYSICS_DT and steps < MAX_STEPS_PER_FRAME:
            physics_step()
            accumulator -= PHYSICS_DT
            steps += 1
        if steps == MAX_STEPS_PER_FRAME:
            accumulator = 0.0

    update_history(dt)
    refresh_visuals()


# ============================================================
# Events
# ============================================================

@window.event
def on_draw():
    window.clear()
    bg_batch.draw()
    sim_batch.draw()
    ui_batch.draw()
    chart_batch.draw()
    text_batch.draw()


@window.event
def on_mouse_press(x, y, button, modifiers):
    global mode, running, formula_focused, formula_cursor, formula_select_all, formula_view_start
    if button != mouse.LEFT:
        return

    if manual_btn.hit(x, y):
        mode = "manual"
        manual_btn.set_active(True)
        formula_btn.set_active(False)
        formula_focused = False
        refresh_formula_display()
        return

    if formula_btn.hit(x, y):
        mode = "formula"
        manual_btn.set_active(False)
        formula_btn.set_active(True)
        formula_focused = False
        refresh_formula_display()
        return

    if run_btn.hit(x, y):
        running = not running
        run_btn.set_text("PAUSE" if running else "RUN")
        status_label.text = "RUNNING" if running else "PAUSED"
        status_label.color = (C_ACCENT_2 + (255,)) if running else (C_WARN + (255,))
        return

    if reset_btn.hit(x, y):
        reset_simulation()
        return

    if disturb_btn.hit(x, y):
        disturb()
        return

    if (PANEL_X + 37 <= x <= PANEL_X + 363 and 486 <= y <= 522):
        formula_focused = True
        formula_select_all = False

        # Consolas 10pt is close enough to fixed-width for click placement.
        text_left = PANEL_X + 48
        approx_char_px = 7.0
        clicked_index = formula_view_start + int(round((x - text_left) / approx_char_px))
        formula_cursor = max(0, min(clicked_index, len(formula_text)))
        refresh_formula_display()
    else:
        formula_focused = False
        formula_select_all = False
        refresh_formula_display()


@window.event
def on_text(text):
    global formula_text, formula_cursor, formula_select_all
    if not formula_focused:
        return

    # Keep it one-line, but allow insertion at the cursor.
    if text and text not in ("\r", "\n", "\t"):
        if formula_select_all:
            formula_text = ""
            formula_cursor = 0
            formula_select_all = False

        formula_text = (
            formula_text[:formula_cursor]
            + text
            + formula_text[formula_cursor:]
        )
        formula_cursor += len(text)
        refresh_formula_display()


@window.event
def on_key_press(symbol, modifiers):
    global running, left_down, right_down
    global formula_text, formula_focused, formula_cursor, formula_select_all

    if formula_focused:
        ctrl = bool(modifiers & key.MOD_CTRL)

        if ctrl and symbol == key.A:
            formula_select_all = True
            formula_cursor = len(formula_text)
            refresh_formula_display()
            return

        if symbol == key.LEFT:
            formula_select_all = False
            formula_cursor = max(0, formula_cursor - 1)
            refresh_formula_display()
            return

        if symbol == key.RIGHT:
            formula_select_all = False
            formula_cursor = min(len(formula_text), formula_cursor + 1)
            refresh_formula_display()
            return

        if symbol == key.HOME:
            formula_select_all = False
            formula_cursor = 0
            refresh_formula_display()
            return

        if symbol == key.END:
            formula_select_all = False
            formula_cursor = len(formula_text)
            refresh_formula_display()
            return

        if symbol == key.BACKSPACE:
            if formula_select_all:
                formula_text = ""
                formula_cursor = 0
                formula_select_all = False
            elif formula_cursor > 0:
                formula_text = (
                    formula_text[:formula_cursor - 1]
                    + formula_text[formula_cursor:]
                )
                formula_cursor -= 1
            refresh_formula_display()
            return

        if symbol == key.DELETE:
            if formula_select_all:
                formula_text = ""
                formula_cursor = 0
                formula_select_all = False
            elif formula_cursor < len(formula_text):
                formula_text = (
                    formula_text[:formula_cursor]
                    + formula_text[formula_cursor + 1:]
                )
            refresh_formula_display()
            return

        if symbol in (key.ENTER, key.NUM_ENTER):
            apply_formula()
            formula_focused = False
            formula_select_all = False
            refresh_formula_display()
            return

        if symbol == key.ESCAPE:
            formula_focused = False
            formula_select_all = False
            refresh_formula_display()
            return

        # While editing, arrow keys belong to the editor, not manual control.
        return

    if symbol == key.LEFT:
        left_down = True
    elif symbol == key.RIGHT:
        right_down = True
    elif symbol == key.SPACE:
        running = not running
        run_btn.set_text("PAUSE" if running else "RUN")
        status_label.text = "RUNNING" if running else "PAUSED"
        status_label.color = (C_ACCENT_2 + (255,)) if running else (C_WARN + (255,))
    elif symbol == key.R:
        reset_simulation()


@window.event
def on_key_release(symbol, modifiers):
    global left_down, right_down
    if symbol == key.LEFT:
        left_down = False
    elif symbol == key.RIGHT:
        right_down = False


# ============================================================
# Start
# ============================================================

apply_formula()
reset_simulation()
pyglet.clock.schedule(update)
pyglet.app.run()

