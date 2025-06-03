import os
import time
from .SubState import NoahsTavernSub
from ..BotState import BotState
from ..FinishState import FinishState


TEMPLATE_REF_DIR = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..',
            'config',
            'reference_images'
        )
    )


class NoahsTavern(BotState):
    def __init__(self, bot):
        super().__init__(
            bot,
            template_ref_dir=TEMPLATE_REF_DIR
        )

    def handle(self):
        if self.bot.substate is None:
            self.init()
        elif self.bot.substate == NoahsTavernSub.SKIP_HEROE:
            self.skip_heroe()
        elif self.bot.substate == NoahsTavernSub.SKIP_ALL:
            self.skip_all()
        elif self.bot.substate == NoahsTavernSub.EXIT:
            self.exit()

    def init(self):
        time.sleep(1)
        self.bot.change_substate(NoahsTavernSub.SKIP_HEROE)

    def skip_heroe(self):
        res = self.wait_for_templates(
            target_refs=[
                'skip_heroes_1',
                'skip_heroes_2'
            ],
            stop_refs=[
                'noahs_all'
            ],
            retry_delay=2,
            timeout=8
        )
        if res is None:
            self.bot.memu.click_percent(0.25, 0.80, sleep_range=(5.1, 5.2))
            self.bot.change_substate(NoahsTavernSub.SKIP_ALL)
        elif res:
            self.bot.memu.click_percent(0.51, 0.90, sleep_range=(5.1, 5.2))

    def skip_all(self):
        self.bot.memu.click_percent(0.02, 0.01, sleep_range=(7.1, 7.2))
        self.bot.memu.click_percent(0.49, 0.50, sleep_range=(9.1, 9.2))
        self.bot.memu.click_percent(0.49, 0.50, sleep_range=(9.1, 9.2))
        self.bot.memu.click_percent(0.49, 0.50, sleep_range=(9.1, 9.2))
        self.bot.memu.click_percent(0.93, 0.96, sleep_range=(7.1, 7.2))
        if self.wait_for_templates(
            target_refs=[
                'noahs_finish_1',
                'noahs_finish_2',
                'noahs_finish_3'
            ],
            stop_refs=[],
            timeout=8
        ):
            self.bot.change_substate(NoahsTavernSub.EXIT)

    def exit(self):
        self.bot.change_state(FinishState(self.bot))
