from __future__ import annotations

import multiprocessing
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


URL = "https://chat.deepseek.com/sign_up"

OUTPUT = Path(
    "../aiodeepseek/data/device_ids.py"
)

PROCESSES = 5

IDS_PER_PROCESS = 100


def build_driver() -> webdriver.Chrome:
    options = Options()

    options.add_argument("--incognito")

    options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    options.add_argument("--no-sandbox")

    options.add_argument(
        "--disable-dev-shm-usage"
    )

    options.add_argument(
        "--disable-infobars"
    )

    options.add_argument(
        "--disable-notifications"
    )

    options.add_argument(
        "--start-maximized"
    )

    return webdriver.Chrome(
        service=Service(
            ChromeDriverManager().install()
        ),
        options=options,
    )


def ensure_module() -> None:
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if OUTPUT.exists():
        return

    OUTPUT.write_text(
        (
            "from __future__ import annotations\n\n"
            "import random\n"
            "from typing import List\n\n"
            "DEVICE_IDS: List[str] = [\n"
            "]\n\n"
            "def get_device_id() -> str:\n"
            "    return random.choice(DEVICE_IDS)\n"
        ),
        encoding="utf-8",
    )


def append_device_id(
    lock: multiprocessing.Lock,
    device_id: str,
) -> None:
    with lock:
        text = OUTPUT.read_text(
            encoding="utf-8",
        )

        if device_id in text:
            return

        marker = (
            "DEVICE_IDS: List[str] = ["
        )

        start = text.index(marker)

        insert_pos = (
            start + len(marker)
        )

        updated = (
            text[:insert_pos]
            + f'\n    "{device_id}",'
            + text[insert_pos:]
        )

        OUTPUT.write_text(
            updated,
            encoding="utf-8",
        )


def fetch_device_id(
    driver: webdriver.Chrome,
) -> str:
    driver.get(URL)

    script = """
const callback = arguments[0];

(async () => {

    function waitForSMSdk() {

        return new Promise(resolve => {

            const interval = setInterval(() => {

                if (
                    window.SMSdk &&
                    window.SMSdk.ready &&
                    window.SMSdk.getDeviceId
                ) {

                    clearInterval(interval);

                    resolve();

                }

            }, 100);

        });

    }

    await waitForSMSdk();

    const deviceId =
        await new Promise(resolve => {

            window.SMSdk.ready(() => {

                resolve(
                    window.SMSdk.getDeviceId()
                );

            });

        });

    callback(deviceId);

})();
"""

    return driver.execute_async_script(
        script
    )


def worker(
    worker_id: int,
    lock: multiprocessing.Lock,
) -> None:
    driver = build_driver()

    try:
        for i in range(
            IDS_PER_PROCESS
        ):
            try:
                device_id = fetch_device_id(
                    driver
                )

                print(
                    f"[P{worker_id}] "
                    f"[{i + 1}] "
                    f"{device_id}"
                )

                append_device_id(
                    lock,
                    device_id,
                )

            except Exception as e:
                print(
                    f"[P{worker_id}] ERROR: {e}"
                )

            time.sleep(
                random.uniform(
                    0.3,
                    1.2,
                )
            )

    finally:
        driver.quit()


def main() -> None:
    ensure_module()

    lock = multiprocessing.Lock()

    processes: list[
        multiprocessing.Process
    ] = []

    for i in range(PROCESSES):
        p = multiprocessing.Process(
            target=worker,
            args=(
                i + 1,
                lock,
            ),
        )

        p.start()

        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    main()