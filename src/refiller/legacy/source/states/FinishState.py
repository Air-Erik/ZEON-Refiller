import os
from .BotState import BotState


class FinishState(BotState):
    def handle(self):
        pass


class FinishLogin(BotState):
    def handle(self):
        user_name = self.bot.db.get_user_name_by_account_id(
            self.bot.game_account_id
        )
        vm_env_prefix = os.getenv("VM_PREFIX", "Prod").strip()
        new_vm_name = f'[{vm_env_prefix}] {user_name}_{self.bot.game_account_name}'

        self.bot.v_sphere.rename_vm(self.bot.vm, new_vm_name)

        new_folder_name = f"DC1/ZeonVM/{vm_env_prefix}/UserVMs"
        self.bot.v_sphere.move_vm_to_folder(self.bot.vm, new_folder_name)

        data = {
            'emulator_name': new_vm_name,
            'port': self.bot.ip
        }

        self.bot.db.create_or_update_emulator(
            self.bot.game_account_id,
            data
        )

        self.bot.change_state(FinishState(self.bot))
