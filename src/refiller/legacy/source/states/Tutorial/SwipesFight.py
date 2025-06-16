import os
from .SubState import SpiderEscapeSub
from ..BotState import BotState


TEMPLATE_REF_DIR = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..',
            'config',
            'reference_images'
        )
    )


class SwipesFight(BotState):
    def __init__(self, bot):
        super().__init__(
            bot,
            template_ref_dir=TEMPLATE_REF_DIR
        )

    def handle(self):
        if self.bot.substate is None:
            self.init()
        elif self.bot.substate == SpiderEscapeSub.FIRST:
            self.swipes()

    def init(self):
        if self.wait_for_template(
            'spider_notification_skip',
            retry_delay=5,
            timeout=15
        ):
            self.bot.memu.click_percent(0.73, 0.35)
            self.logger.info('Уведомление закрыто')

        self.bot.memu.swipe_percent(
            [0.17, 0.89],
            [0.82, 0.89],
            sleep_range=(3.1, 3.3)
        )
        self.bot.change_substate(SpiderEscapeSub.FIRST)
