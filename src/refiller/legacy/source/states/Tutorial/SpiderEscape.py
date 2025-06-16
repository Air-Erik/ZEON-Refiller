import os
from .MatchThree import MatchThree
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


class SpiderEscape(BotState):
    def __init__(self, bot):
        super().__init__(
            bot,
            template_ref_dir=TEMPLATE_REF_DIR
        )

    def handle(self):
        if self.bot.substate is None:
            self.init()
        elif self.bot.substate == SpiderEscapeSub.FIRST:
            self.first_swipe()
        elif self.bot.substate == SpiderEscapeSub.SECOND:
            self.second_swipe()
        elif self.bot.substate == SpiderEscapeSub.THIRD:
            self.third_swipe()
        elif self.bot.substate == SpiderEscapeSub.EXIT:
            self.exit()

    def init(self):
        if self.wait_for_template(
            'spider_notification_skip',
            retry_delay=5,
            timeout=15
        ):
            self.bot.memu.click_percent(0.73, 0.35)
            self.logger.info('Уведомление закрыто')

        self.bot.memu.swipe_percent(
            [0.78, 0.44],
            [0.78, 0.53],
            sleep_range=(15.1, 15.3)
        )
        self.bot.change_substate(SpiderEscapeSub.FIRST)

    def first_swipe(self):
        res = self.wait_for_template(
            ref_name='spider_1',
            stop_ref_name='spider_lose',
            retry_delay=1,
            timeout=20
        )

        if res is None:
            self._phase_failure()
        elif res:
            self.logger.debug('Этап инициализации успешно пройден. Приступаем к этапу 1')
            # self.bot.memu.click_percent(0.5, 0.51, sleep_range=(0.2, 0.2))
            self.bot.memu.swipe_percent(
                [0.75, 0.85], [0.75, 0.77],
                sleep_range=(0.9, 1.1),
                duration_range=(0.25, 0.25)
            )
            self.bot.memu.swipe_percent(
                [0.33, 0.77], [0.47, 0.77],
                sleep_range=(5.1, 5.3),
                duration_range=(0.25, 0.25)
            )
            self.bot.change_substate(SpiderEscapeSub.SECOND)
        else:
            ...

    def second_swipe(self):
        res = self.wait_for_template(
            ref_name='spider_2',
            stop_ref_name='spider_lose',
            retry_delay=5,
            timeout=60
        )

        if res is None:
            self._phase_failure()
        elif res:
            self.logger.debug('Этап 1 успешно пройден. Приступаем к этапу 2')
            # self.bot.memu.click_percent(0.5, 0.51, sleep_range=(0.2, 0.2))
            # Дублирование свайпа для надежности
            self.bot.memu.swipe_percent(
                [0.18, 0.28],
                [0.33, 0.28],
                duration_range=(0.25, 0.22)
            )
            self.bot.memu.swipe_percent(
                [0.18, 0.28],
                [0.33, 0.28],
                sleep_range=(9.1, 9.2),
                duration_range=(0.25, 0.25)
            )
            self.bot.change_substate(SpiderEscapeSub.THIRD)
        else:
            ...

    def third_swipe(self):
        res = self.wait_for_template(
            ref_name='spider_3',
            stop_ref_name='spider_lose',
            retry_delay=1,
            timeout=20
        )

        if res is None:
            self._phase_failure()
        elif res:
            self.logger.debug('Этап 2 успешно пройден. Приступаем к этапу 3')
            # self.bot.memu.click_percent(0.5, 0.51, sleep_range=(0.2, 0.2))
            # Дублирование свайпа для надежности
            self.bot.memu.swipe_percent(
                [0.34, 0.72], [0.34, 0.63],
                duration_range=(0.21, 0.22)
            )
            self.bot.memu.swipe_percent(
                [0.34, 0.72], [0.34, 0.63],
                sleep_range=(4.1, 4.2),
                duration_range=(0.21, 0.22)
            )
            self.bot.change_substate(SpiderEscapeSub.EXIT)
        else:
            ...

    def exit(self):
        res = self.wait_for_template(
            ref_name='spider_exit',
            stop_ref_name='spider_lose',
            retry_delay=5,
            timeout=60
        )

        if res is None:
            self._phase_failure()
        elif res:
            self.logger.info('Этап 3 успешно пройден. Паук пройден!')
            self.bot.change_state(MatchThree(self.bot))
        else:
            ...

    def _phase_failure(self):
        self.logger.info('Паук победил. Перезапуск')
        self.bot.memu.click_percent(0.49, 0.49, sleep_range=(4.1, 4.2))
        self.bot.change_substate(SpiderEscapeSub.FIRST)
