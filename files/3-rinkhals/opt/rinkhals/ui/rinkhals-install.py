import os
import time
import threading
import sys
import traceback

import lvgl as lv


def run_async(callback):
    t = threading.Thread(target=callback)
    t.start()


SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))


def init():
    lv.init()

    if lv.helpers.is_windows():
        display = lv.windows_create_display('Rinkhals', 272, 480, 80, False, True)
        touch = lv.windows_acquire_pointer_indev(display)
        touch.set_display(display)

    elif lv.helpers.is_linux():
        display = lv.linux_fbdev_create()
        lv.linux_fbdev_set_file(display, '/dev/fb0')

        rot = lv.DISPLAY_ROTATION._270
        display.set_rotation(rot)

        touch = lv.evdev_create(lv.INDEV_TYPE.POINTER, '/dev/input/event0')
        touch.set_display(display)

        # TODO Fine-tune calibration
        TOUCH_MAX_X = 460
        TOUCH_MAX_Y = 25
        TOUCH_MIN_X = 25
        TOUCH_MIN_Y = 235

        lv.evdev_set_calibration(touch, TOUCH_MIN_X, TOUCH_MIN_Y, TOUCH_MAX_X, TOUCH_MAX_Y)

    #display.set_theme(lvr.theme)
    display.set_dpi(130)

    global lvr
    import lvgl_rinkhals as lvr


def layout():
    def event_callback(event):
        pass

    # Main screen
    screen_main = lvr.screen()
    if screen_main:
        container_buttons = lvr.flex_container(screen_main, align=lv.FLEX_ALIGN.CENTER)
        container_buttons.set_size(lv.pct(100), lv.pct(100))

        rinkhals_icon = lvr.image(container_buttons)
        rinkhals_icon.set_src(SCRIPT_PATH + '/icon.png')
        lvr.scale_image(rinkhals_icon, lv.dpx(80))

        label_test = lvr.label(container_buttons)
        label_test.set_text('Test 123456')

        def update_label():
            i = 0
            while True:
                i = i + 1
                time.sleep(0.5)
                lv.lock()
                label_test.set_text(f'Test {i}')
                lv.unlock()

        run_async(update_label)

        button_apps = lvr.button(container_buttons)
        button_apps.set_width(lv.pct(100))
        button_apps_label = lv.label(button_apps)
        button_apps_label.set_text('Manage apps')
        button_apps_label.center()
        
        button_settings = lvr.button(container_buttons)
        button_settings.set_width(lv.pct(100))
        button_settings_label = lv.label(button_settings)
        button_settings_label.set_text('Advanced settings')
        button_settings_label.center()
        
        button_test = lvr.button(container_buttons)
        button_test.set_width(lv.pct(100))
        button_test_label = lv.label(button_test)
        button_test_label.set_text('')
        button_test_label.set_style_text_font(lvr.font_icon, lv.STATE_DEFAULT)
        button_test_label.center()

    # Apps screen
    screen_apps = lvr.screen()
    if screen_apps:
        pass

    lv.screen_load(screen_main)
    

def main():
    init()
    layout()

    while True:
        lv.tick_inc(16)
        lv.timer_handler()
        time.sleep(0.016)


if __name__ == "__main__":
    try:
        main()
    except:
        frames = sys._current_frames()
        threads = {}
        for thread in threading.enumerate():
            threads[thread.ident] = thread
        for thread_id, stack in frames.items():
            if thread_id == threading.main_thread().ident:
                print(traceback.format_exc())
            else:
                print(f'-- Thread {thread_id}: {threads[thread_id]} --')
                print(' '.join(traceback.format_list(traceback.extract_stack(stack))))
            
    print('', flush=True)
    os.kill(os.getpid(), 9)
