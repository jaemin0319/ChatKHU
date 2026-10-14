"""Two-window demo: MuJoCo passive viewer (free camera) + OpenCV monitor window.

Monitor = a camera frame (sim render of `--camera`, or a real camera with `--video`) with the path
drawn as a 2-D graph projected through a calibrated camera model (`--monitor-calib`, default: the
exact model of the sim camera). The planner overlay is NOT drawn into the frame's 3-D scene, so the
same view works on a real camera image. The MuJoCo viewer keeps its 3-D overlay.

Commands come from the side_cam (OpenCV) window: click its button bar, or press the key while
that window has keyboard focus:
  N new seeded target   S select shown path   V request validation   Y approve & execute
  H return path to ready   X cancel/stop (also cancels a drag)   U undo  R redo  O original path   Q quit
Path editing (side_cam image area): left-press near a path point picks it, dragging changes only its
height: x, y stay fixed and z is the point of the vertical line through it that is closest to the
mouse ray (real side_cam pose/fovy), release keeps the edit,
right-click cancels the drag. Any edit clears validation/approval: S, V, Y are needed again.
Keys pressed in the MuJoCo window are MuJoCo's own shortcuts (S shadow, V tendon, H hull, ...),
NOT these commands. The MuJoCo window keeps its mouse camera controls (and Ctrl+drag perturbation).
Without --target-r the first seeded target is generated at start (selection/validation/approval
are still required).

Both windows draw the same Overlay built from the same MjData instant (see overlay.py);
the sim time and frame number are printed in both.

  python -m pinch_sim.app --target-r 0.275 --target-deg 0
  python -m pinch_sim.app --seed 7
  python -m pinch_sim.app --target-r 0.275 --target-deg 0 --work-height -0.02 --allow-unsafe-test-geometry
  python -m pinch_sim.app ... --script "2:S,3:V,8:Y,20:Q"   (scripted key presses at wall-clock seconds,
                                                            for unattended GUI smoke tests)
  --script "2:DRAG:0.4:30:-20"  scripted mouse drag through the same mouse handler: press on the path
                                point at 40 % of its samples, move by (+30, -20) display pixels, release
  --voice-gateway [SOCKET]      accept the voice process (쿠옹이, manipulator_voice.kuong_sim) on a local
                                socket; its commands run in this main loop through the same Session
                                methods as the buttons (default socket $XDG_RUNTIME_DIR/pinch_sim/voice.sock)
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
import threading
import time

os.environ.setdefault("MUJOCO_GL", "egl")   # offscreen Renderer on EGL, independent of the viewer's GLFW

import cv2  # noqa: E402
import mujoco  # noqa: E402
import mujoco.viewer  # noqa: E402
import numpy as np  # noqa: E402

from .model import ROOT, load_config, load_scene, ready_q, with_overrides  # noqa: E402
from .camera_model import CameraModel  # noqa: E402
from .monitor import SimFrameSource, VideoFrameSource, draw_overlay_2d  # noqa: E402
from .overlay import add_overlay, build_overlay, peak_text  # noqa: E402
from .screen import pick_index, pixel_to_vertical  # noqa: E402
from .session import EDITABLE, KOREAN, Session  # noqa: E402
from .ui import MonitorUI, Notices, arrange_viewer, auto_layout, monitors, notice_text, protect_points, window_pos  # noqa: E402
from .voice_gateway import VoiceGateway  # noqa: E402

WIN = "side_cam (click buttons / keys here)"
BUTTONS = (("N", "new"), ("S", "select"), ("V", "valid"), ("Y", "RUN"), ("H", "home"), ("X", "stop"),
           ("U", "undo"), ("R", "redo"), ("O", "orig"), ("Q", "quit"))
BAR_H = 36                       # button bar at the bottom of the side_cam window (= ui.Layout.bar_h)
ENABLED = {"N": lambda st: st not in ("EXECUTING", "VALIDATING"), "S": lambda st: st == "GENERATED",
           "V": lambda st: st in ("SELECTED", "FAILED"), "Y": lambda st: st == "PASSED",
           "H": lambda st: st in ("HOLD", "DONE", "ABORTED"), "X": lambda st: True, "Q": lambda st: True,
           "U": lambda st: st in EDITABLE, "R": lambda st: st in EDITABLE, "O": lambda st: st in EDITABLE}


def button_at(x: int, y: int, w: int, h: int) -> str | None:
    """Key of the button under image pixel (x, y) of a w x h side_cam image, or None."""
    if not (h - BAR_H <= y < h and 0 <= x < w):
        return None
    return BUTTONS[min(len(BUTTONS) - 1, int(x * len(BUTTONS) / w))][0]


def parse_script(s: str | None) -> list[tuple[float, str]]:
    """'t:KEY', 't:DRAG:frac:dx:dy' or 't:CLICK:frac' items, sorted by wall-clock seconds."""
    if not s:
        return []
    out = []
    for item in s.split(","):
        t, rest = item.split(":", 1)
        out.append((float(t), rest.strip().upper()))
    return sorted(out, key=lambda x: x[0])


class MouseEditor:
    """side_cam mouse -> world-space edit events for the Session (hand input can replace this class).

    Display pixels (x, y) are divided by the display scale to get camera pixels (u, v), so a
    different --side-scale does not change the geometry. Picking and the height ray use the same
    calibrated CameraModel as the 2-D monitor graph. Invalid rays / heights outside
    editor.input_z_range_m are passed on as None (the editor keeps its last valid preview).
    """

    CLICK_PX = 4.0       # press + release closer than this (displayed pixels) = a click, not a drag

    def __init__(self, cam: CameraModel, cfg, scale: float):
        self.cam, self.scale = cam, scale
        self.radius = cfg["editor"]["selection_radius_px"]
        self.z_range = tuple(cfg["editor"]["input_z_range_m"])
        self.pending: tuple | None = None    # (index, control point, x, y) pressed, not yet a drag

    def _uv(self, x, y):
        return x / self.scale, y / self.scale

    def press(self, session: Session, d, x, y) -> bool:
        """Pick the nearest path point. The drag starts only once the mouse moves (a click selects it)."""
        self.pending = None
        ok, why = session.can_edit()
        if not ok:
            session._emit(f"edit refused: {why}")
            return False
        u, v = self._uv(x, y)
        k = pick_index(session.path.points_m, self.cam, u, v, self.radius)
        if k is None:
            session._emit(f"no interior path point within {self.radius:.0f} px of the click")
            return False
        p = pixel_to_vertical(self.cam, u, v, session.path.points_m[k, :2], self.z_range)
        if p is None:
            session._emit("click ray gives no valid height on the point's vertical line")
            return False
        self.pending = (k, p, x, y)
        return True

    def move(self, session: Session, d, x, y) -> bool:
        if self.pending is not None:
            k, p, x0, y0 = self.pending
            if np.hypot(x - x0, y - y0) < self.CLICK_PX:
                return False
            self.pending = None
            if not session.edit_begin(k, p):
                return False
        if session.edit is None or not session.edit.dragging:
            return False
        u, v = self._uv(x, y)
        p = pixel_to_vertical(self.cam, u, v, session.edit.anchor_xy, self.z_range)
        return session.edit_update(p)

    def release(self, session: Session, d) -> bool:
        """Release after a drag ends it; release without moving selects the point for voice edits."""
        if self.pending is not None:
            k = self.pending[0]
            self.pending = None
            return session.point_select(k)
        return session.edit_end()

    def cancel(self, session: Session) -> bool:
        self.pending = None
        return session.edit_cancel()

    def path_point_display(self, session: Session, d, frac: float):
        P = session.path.points_m
        k = int(round(frac * (len(P) - 1)))
        u, v = self.cam.project(P[k])[0][0]
        return u * self.scale, v * self.scale


def screen_axes(cam: CameraModel) -> dict[str, np.ndarray]:
    """World unit vectors for voice directions, as seen on the monitor (the user looks at this view).

    up/down = world +-Z. right/left = camera right, flattened onto the desk. away/toward_me = camera
    viewing direction, flattened (away = into the screen). The camera is assumed not to look straight down.
    """
    R = np.asarray(cam.R_cw, float)          # rows: camera x (right), y (down), z (forward) in world
    def flat(v):
        v = np.array([v[0], v[1], 0.0])
        return v / np.linalg.norm(v)
    right, away = flat(R[0]), flat(R[2])
    up = np.array([0.0, 0.0, 1.0])
    return {"up": up, "down": -up, "right": right, "left": -right, "away": away, "toward_me": -away}


class LatestTextPusher:
    """Hands the newest viewer text to viewer.set_texts in its own thread (older pending texts are dropped)."""

    def __init__(self, viewer):
        self._viewer, self._latest, self._cv = viewer, None, threading.Condition()
        threading.Thread(target=self._run, name="viewer-texts", daemon=True).start()

    def put(self, text) -> None:
        with self._cv:
            self._latest = text
            self._cv.notify()

    def _run(self) -> None:
        while True:
            with self._cv:
                self._cv.wait_for(lambda: self._latest is not None)
                text, self._latest = self._latest, None
            try:
                if not self._viewer.is_running():
                    return
                self._viewer.set_texts(text)
            except Exception:            # viewer closing: nothing left to show
                return


def start_stall_watch(beat: list, path, limit_s: float = 3.0) -> None:
    """Diagnosis: if the main loop does not come round for limit_s, dump every thread's stack to `path`
    (once per stall) and print a warning. Validation runs in a worker, so normal loops are << limit_s."""
    def run():
        dumped = False
        while True:
            time.sleep(0.5)
            gap = time.perf_counter() - beat[0]
            if gap > limit_s and not dumped:
                with open(path, "a") as f:
                    f.write(f"--- main loop stalled {gap:.1f} s at {time.strftime('%H:%M:%S')} ---\n")
                    f.flush()
                    faulthandler.dump_traceback(f, all_threads=True)
                print(f"WARNING: main loop stalled {gap:.1f} s - thread stacks saved to {path}", flush=True)
                dumped = True
            elif gap <= limit_s and dumped:
                print(f"main loop running again", flush=True)
                dumped = False
    threading.Thread(target=run, name="stall-watch", daemon=True).start()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--target-r", type=float)
    ap.add_argument("--target-deg", type=float)
    ap.add_argument("--work-height", type=float, help="override target.work_height_m (failure demo)")
    ap.add_argument("--allow-unsafe-test-geometry", action="store_true",
                    help="let the path generator create TCP points below tcp_z_min (validation still blocks)")
    ap.add_argument("--script", help="scripted keys 't_s:KEY,...' for unattended smoke tests")
    ap.add_argument("--snapshot-dir", help="save side_cam frames on every state change")
    ap.add_argument("--camera", default="side_cam", choices=["side_cam", "side_cam_alt"],
                    help="fixed camera shown in the second window")
    ap.add_argument("--monitor-calib", help="camera calibration JSON for the monitor (default: the sim camera)")
    ap.add_argument("--video", help="real camera for the monitor: device index or video file (needs --monitor-calib)")
    ap.add_argument("--side-pos", default="auto",
                    help="side_cam window top-left 'x,y' in screen pixels (auto: right edge of the primary monitor)")
    ap.add_argument("--side-scale", default="auto",
                    help="side_cam image scale over the 16:10 render (auto: 1.1 = about twice the old area, "
                         "reduced to fit the monitor)")
    ap.add_argument("--no-arrange", action="store_true",
                    help="do not move/resize the MuJoCo window next to side_cam (default: arrange, X11 only)")
    ap.add_argument("--voice-gateway", nargs="?", const="", metavar="SOCKET",
                    help="accept voice commands (쿠옹이) on a local socket; off by default")
    a = ap.parse_args(argv)

    cfg = load_config()
    if a.work_height is not None:
        if a.work_height < cfg["path"]["tcp_z_min_m"] and not a.allow_unsafe_test_geometry:
            ap.error("--work-height below tcp_z_min_m needs --allow-unsafe-test-geometry")
        cfg = with_overrides(cfg, target={"work_height_m": a.work_height})
    m, idx, sha = load_scene(cfg)
    d = mujoco.MjData(m)
    d.qpos[:] = ready_q(m)
    mujoco.mj_forward(m, d)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    (ROOT / "logs").mkdir(exist_ok=True)
    session = Session(m, idx, sha, cfg, d, seed=a.seed, allow_unsafe=a.allow_unsafe_test_geometry,
                      log_path=ROOT / f"logs/session_{stamp}.jsonl")
    print(f"model {sha[:12]}  MuJoCo {mujoco.__version__}  log logs/session_{stamp}.jsonl")
    if a.target_r is not None:
        session.cmd_fixed_target(a.target_r, a.target_deg or 0.0, d)
    else:
        session.cmd_new_target(d, count_as_new=False)   # first seeded target at start: not a New press

    W, H = cfg["cameras"]["width_px"], cfg["cameras"]["height_px"]
    renderer = mujoco.Renderer(m, H, W)
    # monitor camera model: a real calibration file, or the exact model of the sim camera
    cam_model = CameraModel.load(a.monitor_calib) if a.monitor_calib else \
        CameraModel.from_mujoco(m, d, a.camera, W, H)
    if a.video:
        if not a.monitor_calib:
            ap.error("--video needs --monitor-calib (the path is projected with the real camera's calibration)")
        source = VideoFrameSource(a.video)
        f0 = source.frame()
        if (f0.shape[1], f0.shape[0]) != (cam_model.width, cam_model.height):
            cam_model = cam_model.scaled_to(f0.shape[1], f0.shape[0])
    else:
        source = SimFrameSource(m, renderer, a.camera)
    print(f"monitor: {cam_model.name} {cam_model.width}x{cam_model.height}, "
          f"frames from {'video ' + a.video if a.video else 'sim camera ' + a.camera}", flush=True)
    # 16:10 camera image (render W x H, scaled), progress strip above, buttons below (ui.py)
    mons = monitors()
    layout = auto_layout(cam_model.width, cam_model.height, a.side_scale, mons[0] if mons else None)
    ui = MonitorUI(layout)
    notices = Notices()
    session.listeners.append(lambda ev: notices.push(notice_text(ev, session)))
    win_xy = window_pos(layout, a.side_pos, mons[0] if mons else None)
    # GUI_NORMAL: no Qt zoom/pan toolbar (zooming the image would break the pixel -> ray mapping)
    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    cv2.moveWindow(WIN, *win_xy)
    # the window manager may place the MuJoCo window over it; keep the button bar reachable
    cv2.setWindowProperty(WIN, cv2.WND_PROP_TOPMOST, 1)
    print(f"side_cam window {layout.width}x{layout.height} at {win_xy} (image {layout.img_w}x{layout.img_h}, "
          f"scale {layout.scale}, monitors {mons})", flush=True)
    clicks: list[str] = []
    mouse: list[tuple] = []          # ("press"|"move"|"release"|"cancel", x, y) in displayed-image pixels
    mouse_editor = MouseEditor(cam_model, cfg, layout.scale)
    session.screen_axes = screen_axes(cam_model)     # voice directions = what the user sees on the monitor

    def on_mouse(event, x, y, flags, param):
        xi, yi = layout.to_image(x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            k = button_at(x, y, layout.width, layout.height)
            if k:
                clicks.append(k)
            elif layout.region(x, y) == "image" and not ui.hit_ui(xi, yi):   # bubbles / notice: not an edit
                mouse.append(("press", xi, yi))
        elif event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_LBUTTON:
            if mouse and mouse[-1][0] == "move":
                mouse[-1] = ("move", xi, yi)          # coalesce: only the latest position matters
            else:
                mouse.append(("move", xi, yi))
        elif event == cv2.EVENT_LBUTTONUP:
            mouse.append(("release", xi, yi))
        elif event == cv2.EVENT_RBUTTONDOWN:
            mouse.append(("cancel", xi, yi))

    cv2.setMouseCallback(WIN, on_mouse)
    gateway = VoiceGateway(a.voice_gateway or None, ROOT / f"logs/voice_gateway_{stamp}.jsonl").start(session) \
        if a.voice_gateway is not None else None
    beat = [time.perf_counter()]
    start_stall_watch(beat, ROOT / f"logs/stall_{stamp}.txt")
    script = parse_script(a.script)
    snap_dir = (ROOT / a.snapshot_dir) if a.snapshot_dir else None
    if snap_dir:
        snap_dir.mkdir(parents=True, exist_ok=True)
    render_dt = 1.0 / cfg["app"]["render_hz"]
    frame, last_state, last_render = 0, None, 0.0
    lag_resets = 0
    app_start = time.perf_counter()

    with mujoco.viewer.launch_passive(m, d, show_left_ui=False, show_right_ui=False) as viewer:
        texts = LatestTextPusher(viewer)
        viewer.cam.lookat[:] = [0.0, 0.2, 0.15]
        viewer.cam.distance, viewer.cam.azimuth, viewer.cam.elevation = 1.1, 135, -25
        wall0, sim0 = time.perf_counter(), d.time
        while viewer.is_running():
            now = time.perf_counter()
            beat[0] = now
            target_sim = sim0 + (now - wall0)
            with viewer.lock():
                n = 0
                while d.time < target_sim and n < 200:
                    session.physics_step(d)
                    n += 1
            if n == 200:            # cannot keep real time (e.g. during validation): resync, never skip steps
                wall0, sim0 = time.perf_counter(), d.time
                lag_resets += 1
            session.watch(d)
            if now - last_render < render_dt:
                time.sleep(0.001)
                continue
            last_render = now
            ov = build_overlay(session, d)
            frame += 1
            if frame in (10, 60) and not a.no_arrange:   # the viewer window exists by now; once more in case
                print("window arrange:", arrange_viewer("MuJoCo : 6dof scene", win_xy[0],   # the WM moved it
                                                        mons[0] if mons else None), flush=True)
            with viewer.lock():
                viewer.user_scn.ngeom = 0
                add_overlay(viewer.user_scn, ov)
                source.prepare(d)                    # sim frame: robot + floor only, no 3-D path
                t_sim = float(d.time)
            # set_texts waits for the viewer's render thread to take the texts. Called while holding
            # viewer.lock() that thread can never get the lock -> both stop (stall 2026-10-12). Even outside the
            # lock it waits for seconds when the render thread itself is held up (GNOME Wayland, 2026-10-14:
            # the GLFW window covered by side_cam). So a separate thread pushes the latest text; the main loop
            # (clicks, voice, validation, execution) never waits for the 3-D window.
            texts.put((mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_TOPRIGHT,
                       f"{session.state}\ncommands: side_cam window" + (f"\n{peak_text(ov)}" if ov.peak is not None else ""),
                       f"frame {frame}  t={t_sim:.2f}s\n " + ("\n " if ov.peak is not None else "")))
            viewer.sync()
            img = draw_overlay_2d(source.frame(), cam_model, ov)   # path etc. as a projected 2-D graph
            hint = "" if gateway is None else (gateway.client_line if gateway.connected else "쿠옹이 연결 대기")
            buttons = [(k, label, ENABLED[k](session.state)) for k, label in BUTTONS]
            img = ui.render(img, session, buttons, notices.current(), gateway.chat if gateway else [], hint,
                            protect_points(ov, cam_model, layout.scale))      # bubbles/notices never cover these
            cv2.imshow(WIN, img)
            if snap_dir and session.state != last_state:
                cv2.imwrite(str(snap_dir / f"f{frame:05d}_{session.state}.png"), img)
            last_state = session.state
            key = cv2.waitKey(1) & 0xFF
            keys = [chr(key).upper()] if key not in (255,) and 32 <= key < 127 else []
            keys += clicks
            clicks.clear()
            while script and script[0][0] <= now - app_start:
                item = script.pop(0)[1]
                if item.startswith("DRAG:") and session.path is not None:
                    _, frac, dx, dy = item.split(":")
                    x0, y0 = mouse_editor.path_point_display(session, d, float(frac))
                    mouse.append(("press", x0, y0))
                    mouse.extend(("move", x0 + float(dx) * i / 10, y0 + float(dy) * i / 10) for i in range(1, 11))
                    mouse.append(("release", x0 + float(dx), y0 + float(dy)))
                elif item.startswith("CLICK:") and session.path is not None:
                    x0, y0 = mouse_editor.path_point_display(session, d, float(item.split(":")[1]))
                    mouse.extend([("press", x0, y0), ("release", x0, y0)])
                elif not item.startswith(("DRAG:", "CLICK:")):
                    keys.append(item)
            # mouse edits: one queued event per rendered frame so the drag preview is visible
            if mouse:
                kind, mx, my = mouse.pop(0)
                with session.acting("mouse"):
                    if kind == "press":
                        mouse_editor.press(session, d, mx, my)
                    elif kind == "move":
                        mouse_editor.move(session, d, mx, my)
                    elif kind == "release":
                        mouse_editor.release(session, d)
                    else:
                        mouse_editor.cancel(session)
            for k in keys:
                if k == "Q":
                    viewer.close()
                    break
                print(f"key {k} ({KOREAN[session.state]})", flush=True)
                with session.acting("key"):
                    session.handle_key(k, d)
            if gateway is not None:          # voice requests: same thread, same Session methods, after keys
                gateway.drain(session, d)
            if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
                viewer.close()
    if gateway is not None:
        gateway.close()
    session.close()
    cv2.destroyAllWindows()
    summary = {"frames": frame, "lag_resets": lag_resets, "final_state": session.state, "last_run": session.last_run,
               "events": len(session.events)}
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return summary


if __name__ == "__main__":
    main()
