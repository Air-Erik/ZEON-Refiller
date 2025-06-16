import os
import time
from .NoahsTavern import NoahsTavern
from .SubState import SkipClicksSub
from ..BotState import BotState


TEMPLATE_REF_DIR = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..',
            'config',
            'reference_images'
        )
    )


class SkipClicks(BotState):
    def __init__(self, bot):
        super().__init__(
            bot,
            template_ref_dir=TEMPLATE_REF_DIR
        )

    def handle(self):
        if self.bot.substate is None:
            self.init()
        elif self.bot.substate == SkipClicksSub.BEFORE_TAVERN:
            self.before_tavern()
        elif self.bot.substate == SkipClicksSub.OPEN_TAVERN:
            self.open_tavern()
        elif self.bot.substate == SkipClicksSub.EXIT:
            self.exit()

    def init(self):
        time.sleep(10)
        self.bot.change_substate(SkipClicksSub.BEFORE_TAVERN)

    def before_tavern(self):
        while True:
            self.bot.memu.get_screenshot()
            if self.template_matcher.find(
                self.bot.memu.screenshot,
                'skip_tavern'
            ):
                self.bot.change_substate(SkipClicksSub.OPEN_TAVERN)
                break

            self.bot.memu.click_percent(0.51, 0.52, sleep_range=(7.1, 7.5))

    def open_tavern(self):
        self.bot.memu.click_percent(0.49, 0.51, sleep_range=(5.1, 5.5))
        self.bot.memu.click_percent(0.49, 0.51, sleep_range=(5.1, 5.5))
        self.bot.memu.click_percent(0.49, 0.51, sleep_range=(5.1, 5.5))

        self.bot.memu.click_percent(0.30, 0.78, sleep_range=(5.1, 5.5))
        self.bot.memu.click_percent(0.83, 0.47, sleep_range=(5.1, 5.5))

        self.bot.memu.click_percent(0.49, 0.51, sleep_range=(5.1, 5.5))
        self.bot.memu.click_percent(0.51, 0.52, sleep_range=(5.1, 5.5))
        self.bot.memu.click_percent(0.52, 0.49, sleep_range=(5.1, 5.5))

        self.bot.memu.click_percent(0.69, 0.78, sleep_range=(15.1, 15.5))

        if self.wait_for_templates(
            target_refs=[
                'skip_heroes_1',
                'skip_heroes_2'
            ],
            stop_refs=[],
            retry_delay=5,
            timeout=50
        ):
            self.bot.change_substate(SkipClicksSub.EXIT)

    def exit(self):
        self.bot.change_state(NoahsTavern(self.bot))
