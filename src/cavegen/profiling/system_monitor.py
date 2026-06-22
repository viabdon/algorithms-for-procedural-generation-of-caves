from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

import psutil


@dataclass
class SystemSample:
    timestamp: float
    cpu_percent: float
    rss_bytes: int


@dataclass
class SystemMonitor:
    interval_seconds: float = 0.1
    samples: list[SystemSample] = field(default_factory=list)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        process = psutil.Process(os.getpid())
        process.cpu_percent(interval=None)

        def loop() -> None:
            while not self._stop_event.is_set():
                self.samples.append(
                    SystemSample(
                        timestamp=time.time(),
                        cpu_percent=process.cpu_percent(interval=None),
                        rss_bytes=process.memory_info().rss,
                    )
                )
                time.sleep(self.interval_seconds)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def peak_rss_bytes(self) -> int:
        return max((sample.rss_bytes for sample in self.samples), default=0)
