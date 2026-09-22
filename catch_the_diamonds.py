"""Catch the Diamonds! - a small arcade game drawn with the midpoint line algorithm.

Every shape on screen (the catcher, the falling diamonds, the toolbar buttons
and the score) is rasterised point by point with the midpoint line algorithm,
generalised to all eight zones. OpenGL is only used to plot single points.

Controls:
    Left / Right arrows   move the catcher
    P or Space            pause / resume
    R                     restart
    C                     toggle auto-play (cheat) mode
    Q or Esc              quit
    Mouse                 click the toolbar: restart (teal arrow),
                          pause/resume (amber), quit (red cross)
"""

import random
import time

from OpenGL.GL import *
from OpenGL.GLUT import *

# --- Window and timing -------------------------------------------------------
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 600
FRAME_MS = 16          # ~60 FPS
MAX_DT = 0.1           # longest physics step, e.g. after the window was dragged
POINT_SIZE = 2

# --- Toolbar (clickable strip along the top edge) ----------------------------
TOOLBAR_BOTTOM = 540
RESTART_BUTTON_X = (10, 90)
PAUSE_BUTTON_X = (170, 230)
EXIT_BUTTON_X = (320, 380)

# --- Catcher (a bowl-shaped trapezoid) ---------------------------------------
CATCHER_Y = 30
CATCHER_RIM_HALF_WIDTH = 40
CATCHER_BASE_HALF_WIDTH = 30
CATCHER_HALF_HEIGHT = 10
CATCHER_SPEED = 400    # pixels per second
CATCHER_MIN_X = CATCHER_RIM_HALF_WIDTH
CATCHER_MAX_X = WINDOW_WIDTH - CATCHER_RIM_HALF_WIDTH

# --- Diamond -----------------------------------------------------------------
DIAMOND_HALF_WIDTH = 10
DIAMOND_HALF_HEIGHT = 15
DIAMOND_SPAWN_Y = TOOLBAR_BOTTOM - DIAMOND_HALF_HEIGHT - 5
DIAMOND_START_SPEED = 150  # pixels per second
DIAMOND_SPEED_STEP = 10    # added after every catch
CHEAT_SPEED_MARGIN = 1.1   # auto-play moves 10% faster than strictly needed

# --- Score (seven-segment digits inside the toolbar) -------------------------
DIGIT_WIDTH = 12
DIGIT_HEIGHT = 24
DIGIT_GAP = 8
SCORE_CENTER_X = (PAUSE_BUTTON_X[1] + EXIT_BUTTON_X[0]) // 2
SCORE_Y = 570 - DIGIT_HEIGHT // 2  # vertically centred with the buttons

# Segments lit per digit: a=top, b=upper right, c=lower right, d=bottom,
# e=lower left, f=upper left, g=middle.
SEVEN_SEGMENT_DIGITS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}

# --- Colours -----------------------------------------------------------------
WHITE = (1.0, 1.0, 1.0)
RED = (1.0, 0.0, 0.0)
TEAL = (0.0, 1.0, 1.0)
AMBER = (1.0, 0.75, 0.0)
LIGHT_GREEN = (0.4, 1.0, 0.4)
SCORE_COLOR = (0.85, 0.85, 0.85)

# --- Game state --------------------------------------------------------------
catcher_x = WINDOW_WIDTH / 2
diamond_x = WINDOW_WIDTH / 2
diamond_y = DIAMOND_SPAWN_Y
diamond_speed = DIAMOND_START_SPEED
diamond_color = (1.0, 1.0, 0.0)

score = 0
game_over = False
paused = False
cheat_mode = False
held_keys = set()
last_time = time.perf_counter()

# Offset of the fixed-size play area inside a resized window.
view_offset_x = 0
view_offset_y = 0
window_height = WINDOW_HEIGHT


# --- Midpoint line algorithm -------------------------------------------------
def find_zone(x1, y1, x2, y2):
    """Return the zone (octant, 0-7) the line from (x1, y1) to (x2, y2) lies in."""
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) >= abs(dy):
        if dx >= 0 and dy >= 0: return 0
        if dx < 0 and dy >= 0: return 3
        if dx < 0 and dy < 0: return 4
        return 7
    if dx >= 0 and dy >= 0: return 1
    if dx < 0 and dy >= 0: return 2
    if dx < 0 and dy < 0: return 5
    return 6


def convert_to_zone0(zone, x, y):
    """Map a point from the given zone into zone 0."""
    if zone == 0: return x, y
    if zone == 1: return y, x
    if zone == 2: return y, -x
    if zone == 3: return -x, y
    if zone == 4: return -x, -y
    if zone == 5: return -y, -x
    if zone == 6: return -y, x
    return x, -y


def convert_from_zone0(zone, x, y):
    """Map a point from zone 0 back into the given zone."""
    if zone == 0: return x, y
    if zone == 1: return y, x
    if zone == 2: return -y, x
    if zone == 3: return -x, y
    if zone == 4: return -x, -y
    if zone == 5: return -y, -x
    if zone == 6: return y, -x
    return x, -y


def draw_line(x1, y1, x2, y2):
    """Rasterise a line with the integer midpoint algorithm.

    The line is mapped into zone 0 (0 <= slope <= 1, left to right), drawn there
    with the classic E / NE decision variable, and every plotted pixel is mapped
    back to the original zone.
    """
    x1, y1, x2, y2 = round(x1), round(y1), round(x2), round(y2)
    zone = find_zone(x1, y1, x2, y2)
    x1, y1 = convert_to_zone0(zone, x1, y1)
    x2, y2 = convert_to_zone0(zone, x2, y2)

    dx = x2 - x1
    dy = y2 - y1
    d = 2 * dy - dx
    inc_e = 2 * dy
    inc_ne = 2 * (dy - dx)

    x, y = x1, y1
    glBegin(GL_POINTS)
    while x <= x2:
        glVertex2f(*convert_from_zone0(zone, x, y))
        if d > 0:
            d += inc_ne
            y += 1
        else:
            d += inc_e
        x += 1
    glEnd()


# --- Drawing -----------------------------------------------------------------
def draw_catcher():
    if game_over:
        glColor3f(*RED)
    elif cheat_mode:
        glColor3f(*LIGHT_GREEN)
    else:
        glColor3f(*WHITE)
    top = CATCHER_Y + CATCHER_HALF_HEIGHT
    bottom = CATCHER_Y - CATCHER_HALF_HEIGHT
    rim_left = catcher_x - CATCHER_RIM_HALF_WIDTH
    rim_right = catcher_x + CATCHER_RIM_HALF_WIDTH
    base_left = catcher_x - CATCHER_BASE_HALF_WIDTH
    base_right = catcher_x + CATCHER_BASE_HALF_WIDTH
    draw_line(rim_left, top, rim_right, top)             # rim
    draw_line(base_left, bottom, base_right, bottom)     # base
    draw_line(rim_left, top, base_left, bottom)          # left wall
    draw_line(rim_right, top, base_right, bottom)        # right wall


def draw_diamond():
    glColor3f(*diamond_color)
    top = (diamond_x, diamond_y + DIAMOND_HALF_HEIGHT)
    right = (diamond_x + DIAMOND_HALF_WIDTH, diamond_y)
    bottom = (diamond_x, diamond_y - DIAMOND_HALF_HEIGHT)
    left = (diamond_x - DIAMOND_HALF_WIDTH, diamond_y)
    draw_line(*top, *right)
    draw_line(*right, *bottom)
    draw_line(*bottom, *left)
    draw_line(*left, *top)


def draw_buttons():
    # Restart: left-pointing arrow
    glColor3f(*TEAL)
    draw_line(50, 570, 20, 570)
    draw_line(20, 570, 35, 585)
    draw_line(20, 570, 35, 555)

    # Pause / resume: shows "play" while paused, "pause" while running
    glColor3f(*AMBER)
    if paused:
        draw_line(190, 555, 190, 585)
        draw_line(190, 585, 215, 570)
        draw_line(190, 555, 215, 570)
    else:
        draw_line(190, 555, 190, 585)
        draw_line(210, 555, 210, 585)

    # Exit: cross
    glColor3f(*RED)
    draw_line(335, 555, 365, 585)
    draw_line(335, 585, 365, 555)


def draw_digit(digit, x, y):
    """Draw one seven-segment digit with its bottom-left corner at (x, y)."""
    left, right = x, x + DIGIT_WIDTH
    bottom, middle, top = y, y + DIGIT_HEIGHT // 2, y + DIGIT_HEIGHT
    segments = {
        "a": (left, top, right, top),
        "b": (right, middle, right, top),
        "c": (right, bottom, right, middle),
        "d": (left, bottom, right, bottom),
        "e": (left, bottom, left, middle),
        "f": (left, middle, left, top),
        "g": (left, middle, right, middle),
    }
    for segment in SEVEN_SEGMENT_DIGITS[digit]:
        draw_line(*segments[segment])


def draw_score():
    glColor3f(*SCORE_COLOR)
    text = str(score)
    width = len(text) * (DIGIT_WIDTH + DIGIT_GAP) - DIGIT_GAP
    x = SCORE_CENTER_X - width // 2
    for digit in text:
        draw_digit(digit, x, SCORE_Y)
        x += DIGIT_WIDTH + DIGIT_GAP


def display():
    glClear(GL_COLOR_BUFFER_BIT)
    draw_buttons()
    draw_score()
    draw_catcher()
    if not game_over:
        draw_diamond()
    glutSwapBuffers()


# --- Game logic --------------------------------------------------------------
def spawn_diamond():
    global diamond_x, diamond_y, diamond_color
    diamond_x = random.randint(30, WINDOW_WIDTH - 30)
    diamond_y = DIAMOND_SPAWN_Y
    diamond_color = (random.uniform(0.5, 1.0), random.uniform(0.5, 1.0), random.uniform(0.5, 1.0))


def reset_game():
    global score, game_over, paused, catcher_x, diamond_speed
    score = 0
    game_over = False
    paused = False
    catcher_x = WINDOW_WIDTH / 2
    diamond_speed = DIAMOND_START_SPEED
    spawn_diamond()


def toggle_pause():
    global paused
    if not game_over:
        paused = not paused


def toggle_cheat_mode():
    global cheat_mode
    cheat_mode = not cheat_mode
    print(f"Cheat Mode {'ON' if cheat_mode else 'OFF'}")


def quit_game():
    glutLeaveMainLoop()


def diamond_caught(previous_y):
    """AABB test between the catcher and the area the diamond swept this frame.

    Using the swept area (instead of only the new position) keeps fast diamonds
    from tunnelling through the catcher when a frame takes longer than usual.
    """
    overlaps_x = abs(diamond_x - catcher_x) < CATCHER_RIM_HALF_WIDTH + DIAMOND_HALF_WIDTH
    swept_top = previous_y + DIAMOND_HALF_HEIGHT
    swept_bottom = diamond_y - DIAMOND_HALF_HEIGHT
    overlaps_y = (swept_bottom < CATCHER_Y + CATCHER_HALF_HEIGHT and
                  swept_top > CATCHER_Y - CATCHER_HALF_HEIGHT)
    return overlaps_x and overlaps_y


def move_catcher(dt):
    global catcher_x
    if cheat_mode:
        # Steer towards the diamond fast enough to arrive before it lands.
        distance = diamond_x - catcher_x
        time_to_impact = (diamond_y - CATCHER_Y) / diamond_speed
        if time_to_impact > 0:
            speed = max(CATCHER_SPEED, abs(distance) / time_to_impact * CHEAT_SPEED_MARGIN)
            step = min(abs(distance), speed * dt)
            catcher_x += step if distance > 0 else -step
    else:
        direction = (GLUT_KEY_RIGHT in held_keys) - (GLUT_KEY_LEFT in held_keys)
        catcher_x += direction * CATCHER_SPEED * dt
    catcher_x = min(max(catcher_x, CATCHER_MIN_X), CATCHER_MAX_X)


def update(dt):
    global diamond_y, diamond_speed, score, game_over
    if paused or game_over:
        return

    move_catcher(dt)

    previous_y = diamond_y
    diamond_y -= diamond_speed * dt

    if diamond_caught(previous_y):
        score += 1
        print(f"Score: {score}")
        diamond_speed += DIAMOND_SPEED_STEP
        spawn_diamond()
    elif diamond_y + DIAMOND_HALF_HEIGHT < CATCHER_Y - CATCHER_HALF_HEIGHT:
        game_over = True
        print(f"Game Over! Score: {score}")


def tick(_value):
    """Timer callback: advance the game by the real time elapsed and redraw."""
    global last_time
    now = time.perf_counter()
    dt = min(now - last_time, MAX_DT)
    last_time = now

    update(dt)
    glutPostRedisplay()
    glutTimerFunc(FRAME_MS, tick, 0)


# --- Input -------------------------------------------------------------------
def keyboard(key, x, y):
    key = key.lower()
    if key == b"c":
        toggle_cheat_mode()
    elif key in (b"p", b" "):
        toggle_pause()
    elif key == b"r":
        print("Starting Over")
        reset_game()
    elif key in (b"q", b"\x1b"):
        quit_game()


def special_down(key, x, y):
    held_keys.add(key)


def special_up(key, x, y):
    held_keys.discard(key)


def mouse(button, state, x, y):
    if button != GLUT_LEFT_BUTTON or state != GLUT_DOWN:
        return

    # Window coordinates (origin top-left) -> play-area coordinates (origin bottom-left).
    x -= view_offset_x
    y = window_height - y - view_offset_y
    if not TOOLBAR_BOTTOM <= y <= WINDOW_HEIGHT:
        return

    if RESTART_BUTTON_X[0] <= x <= RESTART_BUTTON_X[1]:
        print("Starting Over")
        reset_game()
    elif PAUSE_BUTTON_X[0] <= x <= PAUSE_BUTTON_X[1]:
        toggle_pause()
    elif EXIT_BUTTON_X[0] <= x <= EXIT_BUTTON_X[1]:
        quit_game()


def reshape(width, height):
    """Keep the play area at its native size, centred in the window.

    The shapes are drawn pixel by pixel, so stretching the view would leave gaps
    between the points; centring keeps them crisp and mouse clicks accurate.
    """
    global view_offset_x, view_offset_y, window_height
    view_offset_x = (width - WINDOW_WIDTH) // 2
    view_offset_y = (height - WINDOW_HEIGHT) // 2
    window_height = height
    glViewport(view_offset_x, view_offset_y, WINDOW_WIDTH, WINDOW_HEIGHT)


# --- Setup -------------------------------------------------------------------
def main():
    glutInit()
    glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutCreateWindow(b"Catch the Diamonds!")
    if glutSetOption:  # freeglut: return from glutMainLoop() instead of exiting
        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glPointSize(POINT_SIZE)

    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(special_down)
    glutSpecialUpFunc(special_up)
    glutIgnoreKeyRepeat(1)
    glutMouseFunc(mouse)

    reset_game()
    glutTimerFunc(FRAME_MS, tick, 0)
    glutMainLoop()
    print(f"Goodbye! Score: {score}")


if __name__ == "__main__":
    main()
