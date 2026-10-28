#!/usr/bin/python3
# Copyright (C) 2026 potemkin666
# See the file COPYING for copying conditions.
# AI-Assisted

"""Input-transparent native Wayland underlay; only fixed local WebM files."""

import os
import signal
import sys
import time

from motionlib import STILL, VIDEOS, take_lock, wallpaper


def main():
    lock = take_lock('player.lock')
    if lock is None:
        return 1
    if len(sys.argv) != 2 or sys.argv[1] not in VIDEOS:
        return 1
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('GdkPixbuf', '2.0')
    gi.require_version('Gst', '1.0')
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import Gdk, GdkPixbuf, GLib, Gst, Gtk, GtkLayerShell

    if not Gtk.init_check()[0] or not GtkLayerShell.is_supported():
        return 1
    Gst.init(None)
    os.nice(10)
    pipeline = Gst.Pipeline.new('dhampiros-local-wallpaper')
    windows, stacks = [], []
    frame_times = {}
    paused_hidden = False
    announced = False

    def element(name):
        result = Gst.ElementFactory.make(name)
        if result is None:
            raise RuntimeError(f'Missing GStreamer element: {name}')
        pipeline.add(result)
        return result

    def quit_player(*_arguments):
        pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()
        return GLib.SOURCE_REMOVE

    def orphaned():
        # EOF means our session owner exited or was killed. Restore the real
        # desktop before releasing the underlay, even after an abrupt death.
        try:
            wallpaper(STILL)
        finally:
            quit_player()

    def command(_stream, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            orphaned()
            return GLib.SOURCE_REMOVE
        if not sys.stdin.readline():
            orphaned()
            return GLib.SOURCE_REMOVE
        quit_player()
        return GLib.SOURCE_REMOVE

    def message(_bus, event):
        nonlocal announced
        if event.type == Gst.MessageType.EOS:
            if not pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 0):
                print('failed', flush=True)
                quit_player()
        elif event.type == Gst.MessageType.ERROR:
            for stack in stacks:
                stack.set_visible_child_name('still')
            print(f'dhampiros-motion: decoder error: {event.parse_error()[0]}', file=sys.stderr)
            print('failed', flush=True)
            pipeline.set_state(Gst.State.NULL)
        elif event.type == Gst.MessageType.ASYNC_DONE:
            for stack in stacks:
                stack.set_visible_child_name('video')
            if not announced:
                announced = True
                print('ready', flush=True)

    def painted(clock):
        nonlocal paused_hidden
        frame_times[clock] = time.monotonic()
        if paused_hidden:
            paused_hidden = False
            pipeline.set_state(Gst.State.PLAYING)

    def visibility_probe():
        nonlocal paused_hidden
        # Wayland withholds surface frame callbacks while outputs are hidden
        # or locked. Probe with an occasional still redraw, not video decode.
        if frame_times and time.monotonic() - max(frame_times.values()) > 5 and not paused_hidden:
            paused_hidden = True
            pipeline.set_state(Gst.State.PAUSED)
        for window in windows:
            window.queue_draw()
        if os.environ.get('DHAMPIROS_MOTION_DEBUG') == '1':
            _result, current, pending = pipeline.get_state(0)
            _ok, position = pipeline.query_position(Gst.Format.TIME)
            print(f'dhampiros-motion: pipeline={current.value_nick} pending={pending.value_nick} position={position} hidden={paused_hidden}', file=sys.stderr)
        return GLib.SOURCE_CONTINUE

    source = element('filesrc')
    source.set_property('location', str(VIDEOS[sys.argv[1]]))
    demux = element('matroskademux')
    decoder = element('vp9dec')
    decoder.set_property('threads', 2)
    convert = element('videoconvert')
    tee = element('tee')
    assert source.link(demux) and decoder.link(convert) and convert.link(tee)

    def video_pad(_demux, pad):
        caps = pad.get_current_caps()
        if caps and caps.to_string().startswith('video/x-vp9'):
            pad.link(decoder.get_static_pad('sink'))

    demux.connect('pad-added', video_pad)
    display = Gdk.Display.get_default()
    if display.get_n_monitors() > 4:
        raise RuntimeError('More than four outputs: retaining the native still wallpaper')
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(STILL))
    for index in range(display.get_n_monitors()):
        monitor = display.get_monitor(index)
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_accept_focus(False)
        window.set_focus_on_map(False)
        GtkLayerShell.init_for_window(window)
        GtkLayerShell.set_namespace(window, 'dhampiros-motion')
        GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BACKGROUND)
        GtkLayerShell.set_monitor(window, monitor)
        GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_exclusive_zone(window, -1)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(window, edge, True)
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.NONE)
        geometry = monitor.get_geometry()
        ratio = max(geometry.width / pixbuf.get_width(), geometry.height / pixbuf.get_height())
        scaled = pixbuf.scale_simple(round(pixbuf.get_width() * ratio), round(pixbuf.get_height() * ratio), GdkPixbuf.InterpType.BILINEAR)
        crop = scaled.new_subpixbuf(max(0, (scaled.get_width() - geometry.width) // 2),
                                  max(0, (scaled.get_height() - geometry.height) // 2), geometry.width, geometry.height)
        stack.add_named(Gtk.Image.new_from_pixbuf(crop), 'still')
        queue = element('queue')
        queue.set_property('max-size-buffers', 2)
        queue.set_property('max-size-bytes', 0)
        queue.set_property('max-size-time', 0)
        queue.set_property('leaky', 2)
        sink = element('gtksink')
        sink.set_property('force-aspect-ratio', True)
        assert tee.link(queue) and queue.link(sink)
        stack.add_named(sink.get_property('widget'), 'video')
        stack.set_visible_child_name('still')
        window.add(stack)
        window.connect('destroy', quit_player)
        window.show_all()
        window.get_window().set_pass_through(True)
        clock = window.get_frame_clock()
        frame_times[clock] = time.monotonic()
        clock.connect('after-paint', painted)
        windows.append(window)
        stacks.append(stack)
    if not windows:
        return 1
    # Monitor topology changes are handled conservatively: the owner restores
    # PCManFM's still. Explicit restart can re-probe the new outputs.
    display.connect('monitor-added', lambda *_: quit_player())
    display.connect('monitor-removed', lambda *_: quit_player())
    settings = Gtk.Settings.get_default()
    if not settings.get_property('gtk-enable-animations'):
        return 1
    settings.connect('notify::gtk-enable-animations', lambda *_: quit_player() if not settings.get_property('gtk-enable-animations') else None)
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect('message', message)
    GLib.timeout_add_seconds(2, visibility_probe)
    GLib.io_add_watch(sys.stdin, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, command)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, quit_player)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, quit_player)
    if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
        return 1
    try:
        Gtk.main()
    finally:
        pipeline.set_state(Gst.State.NULL)
        lock.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'dhampiros-motion: player unavailable: {error}', file=sys.stderr)
        sys.exit(1)
