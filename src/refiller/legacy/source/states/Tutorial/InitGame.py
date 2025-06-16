from ..BotState import BotState
from .SubState import InitGameSub
from .SpiderEscape import SpiderEscape


class InitGame(BotState):

    def __init__(self, bot):
        super().__init__(bot)
        self.max_duration_min = 25

    def handle(self):
        if self.bot.substate is None:
            self.init()
        elif self.bot.substate == InitGameSub.WAIT:
            self.wait()
        elif self.bot.substate == InitGameSub.RESTART:
            self.restart()
        elif self.bot.substate == InitGameSub.EXIT:
            self.exit()

    def init(self):
        self.bot.memu.u2_click_text("Got it", timeout=8, interval=2)

        res = self.wait_for_templates(
            [
                'init_wait'
            ],
            [
                'init_restart_1',
                'init_restart_2',
            ]
        )

        if res is None:
            self.bot.change_substate(InitGameSub.RESTART)
        elif res:
            self.bot.change_substate(InitGameSub.WAIT)
        else:
            self.logger.warning('Не найден ни один из резутатов')

    def wait(self):
        res = self.wait_for_templates(
            [
                'spider_start'
            ],
            [
                'init_restart_1',
                'init_restart_2'
            ],
            retry_delay=60,
            timeout=1200
        )

        if res is None:
            self.bot.change_substate(InitGameSub.RESTART)
        elif res:
            self.bot.change_substate(InitGameSub.EXIT)
        else:
            self.logger.warning('Не найден ни один из резутатов')

    def restart(self):
        self.bot.memu.close_app()
        self.bot.memu.open_app()

        self.bot.change_substate(None)

    def exit(self):
        self.bot.change_state(SpiderEscape(self.bot))
