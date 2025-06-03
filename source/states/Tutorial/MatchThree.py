import os
import time
from .SkipClicks import SkipClicks
from .SubState import MatchThreeSub
from ..BotState import BotState


TEMPLATE_REF_DIR = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..',
            'config',
            'reference_images'
        )
    )


class MatchThree(BotState):
    def __init__(self, bot):
        super().__init__(
            bot,
            template_ref_dir=TEMPLATE_REF_DIR
        )

    def handle(self):
        if self.bot.substate is None:
            self.init()
        elif self.bot.substate == MatchThreeSub.SWIPES:
            self.swipes()
        elif self.bot.substate == MatchThreeSub.HEROES_ULT:
            self.heroes_ult()
        elif self.bot.substate == MatchThreeSub.EXIT:
            self.exit()

    def init(self):
        time.sleep(2)
        self.bot.change_substate(MatchThreeSub.SWIPES)

    def swipes(self):
        self.bot.memu.swipe_percent(
            [0.36, 0.59], [0.36, 0.67],
            sleep_range=(5.1, 5.2),
            duration_range=(0.31, 0.32)
        )
        self.bot.memu.click_percent(0.36, 0.59, sleep_range=(7.1, 7.2))
        self.bot.memu.click_percent(0.36, 0.59, sleep_range=(5.1, 5.2))
        self.bot.memu.swipe_percent(
            [0.63, 0.52], [0.76, 0.52],
            sleep_range=(7.1, 7.2),
            duration_range=(0.31, 0.32)
        )
        self.bot.memu.swipe_percent(
            [0.36, 0.59], [0.50, 0.59],
            sleep_range=(5.1, 5.2),
            duration_range=(0.31, 0.32)
        )
        self.bot.memu.click_percent(0.49, 0.44, sleep_range=(22.1, 22.2))

        if self.wait_for_template(
            ref_name='match_heroes_ult',
            retry_delay=2,
            timeout=8
        ):
            self.bot.change_substate(MatchThreeSub.HEROES_ULT)

    def heroes_ult(self):
        self.bot.memu.swipe_percent(
            [0.49, 0.51], [0.49, 0.44],
            sleep_range=(7.1, 7.2),
            duration_range=(0.31, 0.32)
        )
        self.bot.memu.click_percent(0.49, 0.51, sleep_range=(7.1, 7.2))
        self.bot.memu.click_percent(0.49, 0.44, sleep_range=(7.1, 7.2))

        self.bot.memu.click_percent(0.29, 0.91, sleep_range=(3.1, 3.2))
        self.bot.memu.click_percent(0.49, 0.91, sleep_range=(3.1, 3.2))
        self.bot.memu.click_percent(0.69, 0.91, sleep_range=(5.1, 5.2))

        self.bot.memu.click_percent(0.49, 0.51, sleep_range=(5.1, 5.2))
        self.bot.memu.click_percent(0.52, 0.55, sleep_range=(5.1, 5.2))

        self.bot.memu.click_percent(0.79, 0.91, sleep_range=(9.1, 9.2))
        self.bot.memu.swipe_percent(
            [0.63, 0.51], [0.53, 0.44],
            sleep_range=(7.1, 7.2),
            duration_range=(0.31, 0.32)
        )
        self.bot.memu.click_percent(0.63, 0.44, sleep_range=(5.1, 5.2))

        self.bot.memu.click_percent(0.19, 0.91, sleep_range=(3.1, 3.2))
        self.bot.memu.click_percent(0.39, 0.91, sleep_range=(3.1, 3.2))
        self.bot.memu.click_percent(0.59, 0.91, sleep_range=(3.1, 3.2))

        self.bot.memu.swipe_percent(
            [0.63, 0.51], [0.49, 0.51],
            sleep_range=(7.1, 7.2),
            duration_range=(0.31, 0.32)
        )
        self.bot.memu.click_percent(0.79, 0.91, sleep_range=(30.1, 30.2))

        if self.wait_for_template(
            ref_name='match_exit',
            retry_delay=2,
            timeout=8
        ):
            self.bot.change_substate(MatchThreeSub.EXIT)

    def exit(self):
        self.bot.memu.click_percent(0.76, 0.65, sleep_range=(3.1, 3.2))
        self.bot.memu.click_percent(0.56, 0.55, sleep_range=(3.1, 3.2))
        self.bot.change_state(SkipClicks(self.bot))
