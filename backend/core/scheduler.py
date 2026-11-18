"""Background Cron Scheduler for all registered modules."""
import threading
import time
from datetime import datetime
from .database import cleanup_previous_days
from .module_registry import registry


class CronScheduler:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self.last_tick = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        # Ensure previous day records are cleaned on startup
        cleanup_previous_days(datetime.now().strftime("%Y-%m-%d"))
        for mod in registry.all_modules():
            try:
                mod.on_startup()
            except Exception as e:
                print(f"[Scheduler] Startup error in {mod.module_id}: {e}")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        last_minute_key = ""
        while not self._stop_event.is_set():
            now = datetime.now()
            minute_key = now.strftime("%Y-%m-%d %H:%M")
            if minute_key != last_minute_key:
                last_minute_key = minute_key
                self.last_tick = now.isoformat()
                for mod in registry.all_modules():
                    try:
                        mod.on_cron_tick(now)
                    except Exception as e:
                        print(f"[Scheduler] Cron tick error in {mod.module_id}: {e}")
            time.sleep(15)

    def stop(self):
        self._stop_event.set()


scheduler = CronScheduler()
