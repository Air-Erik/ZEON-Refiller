import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Union
from sqlalchemy.exc import NoResultFound
from .DBmodels import (
    BotSetting,
    BotSettingType,
    BotDailySetting,
    BotDailySettingValue,
    BotSettingValue,
    SettingDefaultValue
)
from .DBrepos import (
    EmulatorRepository,
    GameAccountRepository,
    ZeonUserRepository,
    BotSettingRepository,
    QuestionRepository,
    BotDailySettingRepository,
    DailySettingDefinitionRepository,
    SettingStringValueRepository,
    CharacterRepository
)


class BaseService:
    def __init__(self, db_url: str):
        """
        Базовый сервис, инициализирующий движок и фабрику сессий.

        :param db_url: Строка подключения к базе данных.
        """
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger(self.__class__.__name__)

    @contextmanager
    def get_session(self):
        """
        Контекстный менеджер для управления сессией.
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            self.logger.exception("Ошибка транзакции, выполнен rollback.")
            raise
        finally:
            session.close()

    def get_account_name(self, account_id: uuid.UUID) -> Optional[str]:
        """
        2. Извлекать имя аккаунта (game_account_name) по его id.
        """
        with self.get_session() as session:
            account_repo = GameAccountRepository(session)
            name = account_repo.get_account_name_by_id(account_id)
            return name

    def get_user_name_by_account_id(self, account_id: uuid.UUID) -> Optional[str]:
        """
        3. Извлекать имя пользователя по game_account_id.
        Алгоритм:
            - Сначала получаем GameAccount (zeon_user_id)
            - Затем получаем ZeonUser и берем user_name
        """
        with self.get_session() as session:
            account_repo = GameAccountRepository(session)
            user_repo = ZeonUserRepository(session)

            account = account_repo.get_by_id(account_id)
            if not account or not account.zeon_user_id:
                return None

            user = user_repo.get_by_id(account.zeon_user_id)  # может кинуть NoResultFound()
            return user.user_name

    def get_user_id_by_account_id(self, account_id: uuid.UUID) -> Optional[str]:
        """
        4. Извлекать id пользователя по game_account_id.
        """
        with self.get_session() as session:
            account_repo = GameAccountRepository(session)
            user_id = account_repo.get_user_id_by_account_id(account_id)
            return user_id

    def get_all_character_ids(self, game_account_id: uuid.UUID) -> Optional[List[uuid.UUID]]:
        """
        5. Возвращает список ID всех персонажей для указанного game_account_id.
        Если персонажей нет, возвращает None.
        """
        with self.get_session() as session:
            char_repo = CharacterRepository(session)
            return char_repo.get_all_ids_by_game_account_id(game_account_id)

    def get_active_character_ids(self, game_account_id: uuid.UUID) -> Optional[List[uuid.UUID]]:
        """
        6. Возвращает список ID персонажей для указанного game_account_id,
        у которых is_on равно True. Если таких нет, возвращает None.
        """
        with self.get_session() as session:
            char_repo = CharacterRepository(session)
            return char_repo.get_active_ids_by_game_account_id(game_account_id)

    def get_character_position(self, character_id: uuid.UUID) -> Optional[int]:
        """
        7. По заданному character.id возвращает значение поля position_number.
        Если персонаж не найден, возвращает None.
        """
        with self.get_session() as session:
            char_repo = CharacterRepository(session)
            return char_repo.get_position_by_character_id(character_id)

    def update_all_characters_is_deleted(self, game_account_id: uuid.UUID, is_deleted: bool = True) -> int:
        """
        8. Обновляет значение поля is_deleted для всех персонажей,
        принадлежащих указанному game_account_id. Возвращает количество
        обновлённых записей.
        """
        with self.get_session() as session:
            char_repo = CharacterRepository(session)
            return char_repo.update_is_deleted_by_game_account_id(game_account_id, is_deleted)

    def create_or_update_character(
        self, game_account_id: uuid.UUID, position_number: int,
        character_panel_screen: str, level: int
    ):
        """
        9. Создаёт или обновляет запись в таблице character.
        Если для указанного game_account_id и position_number уже существует
        запись, обновляет поля character_panel_screen и level; иначе создаёт
        новую запись.
        """
        with self.get_session() as session:
            char_repo = CharacterRepository(session)
            return char_repo.create_or_update_character(game_account_id, position_number, character_panel_screen, level)


class DBGameBot(BaseService):
    def __init__(self, db_url: str):
        """
        Сервис для поддержки работы бота.

        :param db_url: Строка подключения к базе данных.
        """
        super().__init__(db_url)
        # Можно добавить дополнительные репозитории или инициализации, если необходимо
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_emulator_name_and_port(self, account_id: uuid.UUID) -> Optional[tuple]:
        """
        1. Извлекать имя и порт эмулятора из таблицы emulator
            по game_account_id из таблицы GameAccount.
        Возвращает (emulator_name, port) или None, если не найдено.
        """
        with self.get_session() as session:
            emulator_repo = EmulatorRepository(session)
            result = emulator_repo.get_name_and_port_by_account_id(account_id)
            return result  # (name, port) или None

    def set_game_account_run(
        self, account_id: uuid.UUID, is_run: bool
    ) -> None:
        """
        3. Устанавливать значение is_run в таблице GameAccount по game_account_id.
        """
        with self.get_session() as session:
            account_repo = GameAccountRepository(session)
            data = {'is_run': is_run}
            try:
                account_repo.update(account_id, data=data)
            except NoResultFound:
                session.rollback()
                self.logger.warning(f"GameAccount с {account_id} не найден")

    # -------------------
    # 1) Методы работы с конфигами
    # -------------------
    def get_config(self, character_id: uuid.UUID) -> Dict[str, Any]:
        """
        5. Получить настройки для конкретного аккаунта.
        Возвращает словарь вида: { code_name: значение }.

        Значение зависит от типа настройки:
            - bool_value (если setting_type=boolean)
            - int_value (если setting_type=integer)
            - string_value (если setting_type=string)
            - time_span_value (если setting_type=time_span)
        """
        with self.get_session() as session:
            bot_setting_repo = BotSettingRepository(session)
            settings_dict = bot_setting_repo.get_settings(character_id)
            self.logger.debug(f'Получены настройки: {settings_dict}')
            return settings_dict

    # -------------------
    # 2) Методы работы с дневными конфигами
    # -------------------
    def get_daily_config(self, character_id: uuid.UUID) -> Dict[str, Any]:
        """
        Возвращает словарь настроек вида: {code_name: значение} для аккаунта.
        Если настройка устарела (не соответствует сегодняшней дате),
        подставляются дефолты и обновляет значения в таблице
        """
        with self.get_session() as session:
            daily_repo = BotDailySettingRepository(session)
            bot_repo = BotSettingRepository(session)

            # (1) Получаем все ежедневные настройки для аккаунта
            daily_settings = daily_repo.get_all_by_account(character_id)

            # (2) Собираем все definition_ids и получаем для них дефолты
            definition_ids = [s.setting_definition_id for s in daily_settings]
            defaults_map = daily_repo.get_default_values_for_definitions(definition_ids)

            # (3) Загрузить все BotSetting для аккаунта (список объектов BotSetting, уже со связями)
            all_bot_settings = bot_repo.get_all_settings_for_account(character_id)

            result_dict: Dict[str, Any] = {}

            # (4) Итерируемся по дневным настройкам
            for ds in daily_settings:
                code_name_str = self._get_code_name(ds.setting_definition.code_name)
                setting_type = ds.setting_definition.setting_type.setting_type_name
                is_multiple = ds.setting_definition.is_multiple

                if self._is_updated_today(ds.last_update):
                    # Актуально → берём реальное значение из BotDailySettingValue
                    self.logger.debug(f'Настройка {code_name_str} актуальна')
                    val = self._extract_from_db_values(
                        ds.bot_daily_setting_values,
                        setting_type,
                        is_multiple
                    )
                else:
                    # Устарело → смотрим логику
                    self.logger.debug(f'Настройка {code_name_str} устарела')
                    if code_name_str in {"arena_tokens_conquest", "arena_tokens", "arsenal_material_speed_up"}:
                        # (а) часть берем из настроек пользователя BotSettingValue
                        val = self._extract_from_bot_setting(
                            all_bot_settings, code_name_str
                        )
                    else:
                        # (б) прочие настройки берём из дефолтов
                        default_values = defaults_map.get(ds.setting_definition_id, [])
                        val = self._extract_defaults(
                            default_values,
                            setting_type,
                            is_multiple
                        )

                    # После того, как мы узнали новое значение, нужно
                    # перезаписать BotDailySettingValue и обновить last_update
                    self._replace_daily_setting_values(
                        session=session,
                        daily_setting=ds,
                        new_value=val,
                        setting_type=setting_type,
                        is_multiple=is_multiple
                    )
                    ds.last_update = datetime.now(timezone.utc)

                # Запоминаем в итоговый словарь
                result_dict[code_name_str] = val

            self.logger.info(f'Получены ежедневные настройки: {result_dict}')
            return result_dict

    def update_daily_config(
        self,
        character_id: uuid.UUID,
        new_values: Dict[str, Union[Any, List[Any]]]
    ) -> None:
        """
        Обновляет (или создаёт) записи в BotDailySetting и BotDailySettingValue
        для указанных настроек.

        new_values: { "code_name": value_or_list }
            - если настройка is_multiple=False, value_or_list будет одним значением,
                например int/bool/str
            - если настройка is_multiple=True, value_or_list будет списком значений.
        """
        with self.get_session() as session:
            # Готовим репозитории
            daily_repo = BotDailySettingRepository(session)
            definition_repo = DailySettingDefinitionRepository(session)
            ssv_repo = SettingStringValueRepository(session)

            # Идем по ключам (строковым именам настроек)
            for code_name_str, raw_value in new_values.items():
                # 1) Ищем DailySettingDefinition по code_name_str
                definition = definition_repo.get_by_code_name_str(code_name_str)
                if not definition:
                    self.logger.warning(
                        f"Не найден DailySettingDefinition для {code_name_str}, пропускаем."
                    )
                    continue

                # 2) Получаем запись для аккаунта и конкретной настройки
                daily_setting = daily_repo.get_daily_setting_by_account_and_definition(
                    character_id, definition.id
                )

                # 2.1) Проверка на актуальность перед вставкой значений
                if not self._is_updated_today(daily_setting.last_update):
                    self.logger.debug(f'Настройка {code_name_str} устарела, нет нужды в обновлении')
                    continue

                # 2.2) Проверяем, есть ли уже BotDailySetting для account_id если нет - создаём
                if not daily_setting:
                    daily_setting = daily_repo.create_bot_daily_setting(
                        character_id, definition.id
                    )

                # 3) Удаляем старые значения (для упрощённого варианта)
                daily_repo.delete_values_for_setting(daily_setting.id)
                daily_setting.last_update = datetime.now(timezone.utc)

                # 4) Определяем, является ли настройка множественной
                is_multiple = definition.is_multiple

                # Чтобы не писать разную логику, делаем список значений:
                if is_multiple:
                    values_list = raw_value if isinstance(raw_value, list) else [raw_value]
                else:
                    # Для single-настроек берём ровно один элемент
                    values_list = [raw_value]

                # 5) Для каждой единицы значения создаём BotDailySettingValue
                for val_item in values_list:
                    # создаём новый объект "строчки"
                    bds_val = BotDailySettingValue(
                        bot_daily_setting_id=daily_setting.id,
                        setting_type=definition.setting_type.setting_type_name
                    )

                    # Записываем нужное поле в зависимости от типа
                    stype = definition.setting_type.setting_type_name
                    if stype == BotSettingType.integer:
                        bds_val.int_value = int(val_item)
                    elif stype == BotSettingType.boolean:
                        bds_val.bool_value = bool(val_item)
                    elif stype in (BotSettingType.string, BotSettingType.time_span):
                        # Создаём/ищем ssv:
                        ssv = ssv_repo.get_by_value(value=str(val_item))
                        bds_val.setting_string_value_id = ssv.id

                    # Добавляем в сессию
                    session.add(bds_val)

                self.logger.info(
                    f"Обновлены(созданы) значения {values_list} "
                    f"для дневной настройки {code_name_str}"
                )

    # -------------------
    # 3) Методы работы с вопросами-ответами
    # -------------------
    def add_question(self, question_text: str, answer_number: int) -> None:
        """
        Добавляет новый вопрос в базу данных.

        :param question_text: Текст вопроса.
        :param answer_number: Номер правильного ответа.
        """
        with self.get_session() as session:
            q_repo = QuestionRepository(session)
            new_question = {
                q_repo.model.question_text.name: question_text,
                q_repo.model.answer_number.name: answer_number
            }

            q_repo.create(new_question)

    def get_correct_answer(self, question_text: str) -> Optional[int]:
        """
        Получает номер правильного ответа по тексту вопроса.

        :param question_text: Текст вопроса.
        :return: Номер правильного ответа или None, если вопрос не найден.
        """

        with self.get_session() as session:
            question_repo = QuestionRepository(session)
            answer = question_repo.get_correct_answer(question_text=question_text)
            return answer

    # -------------------
    # 4) Методы для входа
    # -------------------
    def delete_emulator(self, account_id: Union[int, uuid.UUID]) -> bool:
        """
        1. Удалять эмулятор из таблицы Emulator по game_account_id.
        Возвращает True при успешном удалении, False если эмулятор не найден.
        """
        with self.get_session() as session:
            emulator_repo = EmulatorRepository(session)
            success = emulator_repo.delete_by_account_id(account_id)
            # commit() произойдёт автоматически при выходе из with
            return success

    def delete_game_account_id(self, account_id: uuid.UUID) -> bool:
        """
        Удаляет запись в таблице GameAccount по заданному account_id.
        Возвращает True при успешном удалении, False в случае ошибки.
        """
        with self.get_session() as session:
            account_repo = GameAccountRepository(session)
            success = account_repo.delete_by_account_id(account_id)
            return success

    def create_or_update_emulator(
        self, account_id: Union[int, uuid.UUID], emulator_data: dict
    ):
        """
        2. Создавать или обновлять существующий эмулятор по game_account_id.
        emulator_data может содержать: emulator_name, port, last_launch...
        """
        with self.get_session() as session:
            emulator_repo = EmulatorRepository(session)
            emulator = emulator_repo.create_or_update_by_account_id(
                account_id, emulator_data
            )
            # После выхода из with произойдёт commit()
            return emulator

    # TODO Изменить название метода
    def fill_defaults_for_account(self, character_id: Union[int, uuid.UUID]) -> None:
        """
        Вызывает репозиторий, чтобы заполнить BotSetting и BotSettingValue
        дефолтными значениями. Вся тяжёлая SQLAlchemy-логика - в репозитории.
        """
        with self.get_session() as session:
            bot_setting_repo = BotSettingRepository(session)
            bot_setting_repo.fill_defaults_for_account(character_id)
            # commit() произойдет автоматически при выходе из with

    # TODO Изменить название метода
    def fill_daily_defaults_for_account(self, character_id: uuid.UUID) -> None:
        with self.get_session() as session:
            repo = BotDailySettingRepository(session)

            # (1) Получаем все определения
            all_defs = repo.get_all_definitions()  # List[DailySettingDefinition]

            # (2) Собираем уже имеющиеся definition_id
            existing_ids = repo.get_existing_setting_definition_ids(character_id)  # Set[int]

            # (3) Фильтруем, чтобы найти отсутствующие
            missing_defs = [d for d in all_defs if d.id not in existing_ids]

            # (4) Для каждого отсутствующего определения создаём BotDailySetting
            for daily_def in missing_defs:
                new_bds = repo.create_bot_daily_setting(character_id, daily_def.id)
                # Примечание: объект уже во "flush"-состоянии, у него есть ID

                # (5) Подгрузим дефолтные значения (обычно их может быть несколько)
                def_map = repo.get_default_values_for_definitions([daily_def.id])
                default_vals = def_map.get(daily_def.id, [])  # List[DailySettingDefaultValue]

                if daily_def.is_multiple:
                    # Если настройка множественная, создаём value для КАЖДОГО дефолта
                    for dv in default_vals:
                        repo.create_value_from_default(
                            bot_daily_setting_id=new_bds.id,
                            setting_type=daily_def.setting_type.setting_type_name,
                            default_obj=dv
                        )
                else:
                    # Если настройка одиночная, достаточно первого дефолта (если он есть)
                    if default_vals:
                        dv = default_vals[0]
                        repo.create_value_from_default(
                            bot_daily_setting_id=new_bds.id,
                            setting_type=daily_def.setting_type.setting_type_name,
                            default_obj=dv
                        )

    # -------------------
    # 5) Вспомогательные методы
    # -------------------
    def _replace_daily_setting_values(
        self,
        session: Session,
        daily_setting: BotDailySetting,
        new_value: Union[Any, List[Any]],
        setting_type: str,
        is_multiple: bool
    ) -> None:
        """
        Полностью удаляет старые значения из BotDailySettingValue и вставляет новые.
        Обновляет daily_setting.last_update (эту часть можно делать снаружи).
        """
        # Репозитории можно создать, если нужно
        daily_repo = BotDailySettingRepository(session)
        ssv_repo = SettingStringValueRepository(session)

        # 1) Удаляем старые BotDailySettingValue
        daily_repo.delete_values_for_setting(daily_setting.id)

        # 2) Формируем список значений (если is_multiple=False, делаем список из одного элемента)
        if is_multiple:
            values_list = new_value if isinstance(new_value, list) else [new_value]
        else:
            values_list = [new_value]

        # 3) Создаём новые BotDailySettingValue
        for val_item in values_list:
            bds_val = BotDailySettingValue(
                bot_daily_setting_id=daily_setting.id,
                setting_type=setting_type  # "integer"/"boolean"/"string"/"time_span"
            )

            if setting_type == BotSettingType.integer:
                bds_val.int_value = int(val_item) if val_item is not None else None
            elif setting_type == BotSettingType.boolean:
                bds_val.bool_value = bool(val_item) if val_item is not None else None
            elif setting_type in (BotSettingType.string, BotSettingType.time_span):
                # Для string/time_span нужно работать через SettingStringValue
                if val_item is not None:
                    ssv = ssv_repo.get_by_value(str(val_item))
                    bds_val.setting_string_value_id = ssv.id if ssv else None

            # Добавляем в сессию
            session.add(bds_val)

    def _extract_defaults(
        self,
        default_values: List[SettingDefaultValue],
        setting_type: BotSettingType,
        is_multiple: bool
    ) -> Union[List[Any], Any, None]:
        """
        Извлекает значения по умолчанию в зависимости от типа и множественности.
        """
        # Формируем список значений
        extracted_list = [
            self._extract_any_value(dv, setting_type, is_default=True)
            for dv in default_values
        ]

        if is_multiple:
            return extracted_list
        else:
            return extracted_list[0] if extracted_list else None

    def _extract_from_db_values(
        self,
        daily_setting_values: List[BotDailySettingValue],
        setting_type: BotSettingType,
        is_multiple: bool
    ) -> Union[List[Any], Any, None]:
        """
        Извлекает значения из BotDailySettingValue (реальные, актуальные).
        """
        extracted_list = [
            self._extract_any_value(val, setting_type, is_default=False)
            for val in daily_setting_values
        ]
        if is_multiple:
            return extracted_list
        else:
            return extracted_list[0] if extracted_list else None

    def _extract_any_value(
        self,
        obj: Union[BotSettingValue, SettingDefaultValue],
        setting_type: BotSettingType,
        is_default: bool
    ) -> Union[bool, int, str, None]:
        """
        Унифицированная логика, извлекающая конкретное значение
        (bool, int, str/time_span, None) из obj (либо DefaultValue, либо SettingValue).
        """
        if setting_type == BotSettingType.integer:
            return obj.default_int if is_default else obj.int_value

        elif setting_type == BotSettingType.boolean:
            return obj.default_bool if is_default else obj.bool_value

        elif setting_type in (BotSettingType.string, BotSettingType.time_span):
            # Аналогичная логика, т.к. оба типа хранятся в setting_string_value_id
            ssv_id = obj.setting_string_value_id
            if ssv_id:
                # Если связка уже подгружена (joinedload), то возьмём .value напрямую
                # Иначе fallback
                if hasattr(obj, "setting_string_value") and obj.setting_string_value:
                    return obj.setting_string_value.value
                # Если для time_span отдельное поле (setting_time_span_value),
                # то можно тоже это учесть. Но у нас всё равно лежит в setting_string_value.
                return f"SSV_{ssv_id}"
            return None

        elif setting_type == BotSettingType.time_range:
            return obj.default_time_range_value if is_default else obj.time_range_value
        elif setting_type == BotSettingType.train_lvl:
            return obj.default_time_range_value if is_default else getattr(obj, "train_lvl_value", None)

        # Если не попали в тип, возвращаем None
        return None

    def _extract_from_bot_setting(
        self,
        bot_settings: List[BotSetting],
        code_name_str: str
    ) -> Any:
        """
        Находит в списке BotSetting нужную запись (по code_name),
        и извлекает ИЗ ПЕРВОГО значения (bot_setting_values[0]) то, что нам надо.
        (т.к. arena_* может иметь только одно значение)
        """
        for bs in bot_settings:
            # Обратите внимание, code_name может быть enum или str
            # Если bs.setting_definition.code_name — это enum,
            #   то .value даст строку
            # Если это просто str, сравниваем напрямую
            # Например:
            if hasattr(bs.setting_definition.code_name, "value"):
                bs_code = bs.setting_definition.code_name.value
            else:
                bs_code = bs.setting_definition.code_name

            if bs_code == code_name_str:
                # Нашли нужную BotSetting
                # Предполагаем, что только одно BotSettingValue
                if not bs.bot_setting_values:
                    return None
                val_obj = bs.bot_setting_values[0]
                stype = bs.setting_definition.setting_type.setting_type_name
                return self._extract_any_value(val_obj, stype, is_default=False)

        # Если ничего не нашли
        return None

    def _is_updated_today(self, last_update) -> bool:
        """
        Проверяет, совпадает ли дата last_update с текущей датой (UTC).
        """
        if not last_update:
            return False
        return last_update.date() == datetime.now(timezone.utc).date()

    def _get_code_name(self, enum_or_str) -> str:
        """
        Если code_name — это enum, берём его .value, иначе возвращаем как есть.
        """
        if hasattr(enum_or_str, "value"):
            return enum_or_str.value
        return str(enum_or_str)

    def get_all_game_account_ids(self) -> Optional[List[uuid.UUID]]:
        """
        Извлекает все ID из таблицы GameAccount и возвращает их в виде списка.

        :return: Список UUID или None в случае ошибки.
        """
        with self.get_session() as session:
            repo = GameAccountRepository(session)
            game_accounts = repo.list_all()
            id_list = [account.id for account in game_accounts]
            self.logger.info(f"Извлечено {len(id_list)} ID из GameAccount.")
            return id_list
