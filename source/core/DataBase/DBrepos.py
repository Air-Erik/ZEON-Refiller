# DBrepos.py
import logging
from typing import (
    List, Dict, Any, Set, Optional, Type, TypeVar, Generic, Union, Tuple
)
from sqlalchemy import cast, String
from sqlalchemy.orm import Session, aliased, joinedload, subqueryload
from sqlalchemy.exc import NoResultFound
from .DBmodels import (
    Base,
    Game,
    ZeonUser,
    GameAccount,
    SettingGroup,
    SettingType,
    SettingDefinition,
    SettingStringValue,
    SubsDuration,
    Emulator,
    BotSetting,
    BotSettingValue,
    SettingConstraint,
    SettingConstraintStringValue,
    SettingDefaultValue,
    BotSettingType,
    DailySettingDefinition,
    BotDailySetting,
    BotDailySettingValue,
    DailySettingDefaultValue,
    Translation,
    Question,
    Character
)
import uuid

# Определение обобщенного типа для репозиториев
T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model
        self.logger = logging.getLogger(self.__class__.__name__)

    def create(self, data: Dict[str, Any]) -> T:
        try:
            obj = self.model(**data)
            self.session.add(obj)
            self.session.flush()
            self.logger.info(f"Объект добавлен: {obj}")
            return obj
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"При добавлении объекта произошла ошибка: {e}")
            return None

    def get_by_id(self, obj_id: Union[int, uuid.UUID]) -> Optional[T]:
        obj = self.session.get(self.model, obj_id)
        if not obj:
            self.logger.error(
                f"{self.model.__name__} с {obj_id} не найден. Вызываю ошибку"
            )
            raise NoResultFound()
        self.logger.info(f"Объект найден: {obj}")
        return obj

    def list_all(self) -> List[T]:
        result = self.session.query(self.model).all()
        self.logger.info(f"Найдено {len(result)} объектов для модели {self.model.__name__}")
        return result

    def update(self, obj_id: Union[int, uuid.UUID], data: Dict[str, Any]) -> Optional[T]:
        obj = self.get_by_id(obj_id)

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
                self.logger.debug(f"Установлено {key} = {value}")
            else:
                self.logger.warning(f"Модель {self.model.__name__} не имеет атрибута '{key}'")
        self.logger.info(f"Объект обновлен: {obj}")
        return obj

    def delete(self, obj_id: Union[int, uuid.UUID]) -> bool:
        obj = self.get_by_id(obj_id)

        self.session.delete(obj)
        self.logger.info(f"Объект удален: {obj}")
        return True


# Репозиторий для модели Game
class GameRepository(BaseRepository[Game]):
    def __init__(self, session: Session):
        super().__init__(session, Game)


# Репозиторий для модели SettingType
class SettingTypeRepository(BaseRepository[SettingType]):
    def __init__(self, session: Session):
        super().__init__(session, SettingType)


# Репозиторий для модели ZeonUser
class ZeonUserRepository(BaseRepository[ZeonUser]):
    def __init__(self, session: Session):
        super().__init__(session, ZeonUser)

    def get_user_name_by_id(self, user_id) -> Optional[str]:
        user = self.get_by_id(user_id)
        return user.user_name if user else None


# Репозиторий для модели GameAccount
class GameAccountRepository(BaseRepository[GameAccount]):
    def __init__(self, session: Session):
        super().__init__(session, GameAccount)

    def get_account_name_by_id(self, account_id) -> Optional[str]:
        account = self.get_by_id(account_id)
        return account.game_account_name if account else None

    def get_user_id_by_account_id(self, account_id) -> Optional[str]:
        account = self.get_by_id(account_id)
        if account and account.zeon_user_id:
            return str(account.zeon_user_id)  # или вернуть как UUID
        return None

    def get_user_name_by_game_account_id(self, game_account_id: Union[int, uuid.UUID]) -> Optional[str]:
        """
        Возвращает имя пользователя по ID его аккаунта.
        """
        self.logger.debug(f"Получение имени пользователя для GameAccount ID: {game_account_id}")
        game_account = self.session.query(self.model).options(
            joinedload(self.model.zeon_user)
        ).filter(self.model.id == game_account_id).first()

        if not game_account or not game_account.user:
            self.logger.info(f"Пользователь для GameAccount ID {game_account_id} не найден.")
            return None

        user_name = game_account.zeon_user.user_name  # Предполагается, что у ZeonUser есть поле 'user_name'
        self.logger.info(f"Имя пользователя для GameAccount ID {game_account_id}: {user_name}")
        return user_name

    def delete_by_account_id(self, account_id: uuid.UUID) -> bool:
        """
        Удаляет запись GameAccount по заданному account_id.
        Возвращает True, если запись найдена и удалена, иначе False.
        """
        try:
            account = self.get_by_id(account_id)
            self.session.delete(account)
            self.session.flush()  # чтобы изменения были сразу применены
            self.logger.info(f"GameAccount с id {account_id} успешно удалён.")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при удалении GameAccount с id {account_id}: {e}")
            return False


# Репозиторий для модели SettingGroup
class SettingGroupRepository(BaseRepository[SettingGroup]):
    def __init__(self, session: Session):
        super().__init__(session, SettingGroup)


# Репозиторий для модели SettingStringValue
class SettingStringValueRepository(BaseRepository[SettingStringValue]):
    def __init__(self, session: Session):
        super().__init__(session, SettingStringValue)

    def get_by_value(
        self,
        value: str
    ) -> Optional[SettingStringValue]:
        """
        Возвращает SettingStringValue с конкретным value,
        либо None, если такой нет.
        """
        return (
            self.session.query(SettingStringValue)
            .filter(
                SettingStringValue.value == value,
            )
            .one_or_none()
        )


# Репозиторий для модели SubsDuration
class SubsDurationRepository(BaseRepository[SubsDuration]):
    def __init__(self, session: Session):
        super().__init__(session, SubsDuration)


# Репозиторий для модели Emulator
class EmulatorRepository(BaseRepository[Emulator]):
    def __init__(self, session: Session):
        super().__init__(session, Emulator)

    def get_name_and_port_by_account_id(self, account_id) -> Optional[Tuple[str, int]]:
        """
        Возвращает (emulator_name, port) по game_account_id.
        Если эмулятора нет, вернёт None.
        """
        emulator = (
            self.session.query(Emulator)
            .filter(Emulator.game_account_id == account_id)
            .one_or_none()
        )
        if emulator:
            return emulator.emulator_name, emulator.port
        return None

    def delete_by_account_id(self, account_id: Union[int, uuid.UUID]) -> bool:
        """
        Удалить эмулятор, связанный с указанным game_account_id.
        Возвращает True, если эмулятор был найден и удалён, иначе False.
        """
        emulator = (
            self.session.query(Emulator)
            .filter(Emulator.game_account_id == account_id)
            .one_or_none()
        )
        if emulator:
            self.session.delete(emulator)
            return True
        return False

    def create_or_update_by_account_id(
        self, account_id: Union[int, uuid.UUID], data: dict
    ) -> Emulator:
        """
        Создать новый эмулятор (Emulator) или обновить существующий
        по полю game_account_id.

        data может содержать поля: emulator_name, port, last_launch, ...
        """
        emulator = (
            self.session.query(Emulator)
            .filter(Emulator.game_account_id == account_id)
            .one_or_none()
        )
        if emulator is None:
            # Создаём новую запись
            emulator = Emulator(game_account_id=account_id, **data)
            self.session.add(emulator)
        else:
            # Обновляем существующую запись
            for key, value in data.items():
                setattr(emulator, key, value)
        return emulator


class CharacterRepository(BaseRepository[Character]):
    def __init__(self, session: Session):
        super().__init__(session, Character)

    def get_all_ids_by_game_account_id(self, game_account_id: uuid.UUID) -> Optional[List[uuid.UUID]]:
        """
        Возвращает список ID всех персонажей для указанного game_account_id,
        отсортированный по возрастанию position_number.
        Если персонажей нет, возвращает None.
        """
        results = (
            self.session.query(Character.id)
            .filter(Character.game_account_id == game_account_id)
            .order_by(Character.position_number.asc())
            .all()
        )
        return [row[0] for row in results] if results else None

    def get_active_ids_by_game_account_id(self, game_account_id: uuid.UUID) -> Optional[List[uuid.UUID]]:
        """
        Возвращает список ID активных персонажей (is_on=True) для указанного
        game_account_id, отсортированный по возрастанию position_number.
        Если таких записей нет, возвращает None.
        """
        results = (
            self.session.query(Character.id)
            .filter(
                Character.game_account_id == game_account_id,
                Character.is_on is True,
                Character.is_deleted is False
            )
            .order_by(Character.position_number.desc())
            .all()
        )
        return [row[0] for row in results] if results else None

    def get_position_by_character_id(self, character_id: uuid.UUID) -> Optional[int]:
        """
        По заданному character.id возвращает значение поля position_number.
        Если персонаж не найден, возвращает None.
        """
        result = (
            self.session.query(Character.position_number)
            .filter(Character.id == character_id)
            .one_or_none()
        )
        return result[0] if result else None

    def update_is_deleted_by_id(self, character_id: uuid.UUID, is_deleted: bool = True) -> bool:
        """
        Устанавливает значение поля is_deleted для персонажа с заданным character.id.
        """
        try:
            character = self.get_by_id(character_id)
            character.is_deleted = is_deleted
            self.session.add(character)
            self.session.flush()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении is_deleted для персонажа {character_id}: {e}")
            return False

    def update_is_deleted_by_game_account_id(self, game_account_id: uuid.UUID, is_deleted: bool = True) -> int:
        """
        Устанавливает значение поля is_deleted для всех персонажей с заданным game_account_id.
        Возвращает количество обновлённых записей.
        """
        updated = (
            self.session.query(Character)
            .filter(Character.game_account_id == game_account_id)
            .update({Character.is_deleted: is_deleted}, synchronize_session=False)
        )
        self.session.flush()
        return updated

    def create_or_update_character(
        self, game_account_id: uuid.UUID, position_number: int,
        character_panel_screen: str, level: int
    ) -> Character:
        """
        Создаёт или обновляет запись в таблице character.
        Если для заданного game_account_id и position_number уже существует запись,
        обновляет поля character_panel_screen и level.
        """
        character = (
            self.session.query(Character)
            .filter(
                Character.game_account_id == game_account_id,
                Character.position_number == position_number
            )
            .one_or_none()
        )
        if character:
            character.character_panel_screen = character_panel_screen
            character.level = level
            character.is_deleted = False
            self.logger.info(f"Обновлена запись персонажа: {character.id}")
        else:
            character = Character(
                game_account_id=game_account_id,
                position_number=position_number,
                character_panel_screen=character_panel_screen,
                level=level
            )
            self.session.add(character)
            self.logger.info("Создан новый персонаж.")
        self.session.flush()
        return character.id


# Репозиторий для модели SettingDefinition
class SettingDefinitionRepository(BaseRepository[SettingDefinition]):
    def __init__(self, session: Session):
        super().__init__(session, SettingDefinition)


# Репозиторий для модели BotSetting
class BotSettingRepository(BaseRepository[BotSetting]):
    def __init__(self, session: Session):
        super().__init__(session, BotSetting)

    def get_all_settings_for_account(self, character_id: uuid.UUID) -> List[BotSetting]:
        """
        Возвращает список объектов BotSetting (и связанные сущности) для данного account_id.
        При этом предзагружает:
            - bot_setting_values (и их setting_string_value)
            - setting_definition (и setting_type)
        """
        result = (
            self.session.query(BotSetting)
            .options(
                joinedload(BotSetting.bot_setting_values)
                .joinedload(BotSettingValue.setting_string_value),
                joinedload(BotSetting.setting_definition)
                .joinedload(SettingDefinition.setting_type)
            )
            .filter(BotSetting.character_id == character_id)
            .all()
        )
        return result

    def get_settings(self, character_id) -> Dict[str, Any]:
        """
        Возвращает словарь вида:
            {
            code_name (str): single_value (bool/int/str/None)
            ИЛИ list_of_values (если is_multiple=True)
            }

        Правила:
        - Если is_multiple = False -> одно значение.
        - Если is_multiple = True -> список значений (даже если одна запись).
        - Значение зависит от setting_type (bool_value, int_value, string_value, time_span и т.д.).
        """

        # Делаем два aliased для SettingStringValue,
        # чтобы отличать "string_value" от "time_span_value"
        ssv_str = aliased(SettingStringValue)
        ssv_time = aliased(SettingStringValue)

        # Собираем один запрос
        query = (
            self.session.query(
                SettingDefinition.code_name.label("code_name"),
                SettingDefinition.is_multiple.label("is_multiple"),
                BotSettingValue.setting_type.label("stype"),
                BotSettingValue.bool_value.label("bval"),
                BotSettingValue.int_value.label("ival"),
                ssv_str.value.label("str_value"),
                ssv_time.value.label("time_span_value"),
                BotSettingValue.time_range_value.label("time_range_value"),
                BotSettingValue.train_lvl_value.label("train_lvl_value")
            )
            .select_from(BotSetting)
            .join(SettingDefinition, SettingDefinition.id == BotSetting.setting_definition_id)
            .join(BotSettingValue, BotSettingValue.bot_setting_id == BotSetting.id)
            .outerjoin(ssv_str, ssv_str.id == BotSettingValue.setting_string_value_id)
            .outerjoin(ssv_time, ssv_time.id == BotSettingValue.setting_time_span_value_id)
            .filter(BotSetting.character_id == character_id)
        )

        rows = query.all()

        # Временная структура для группировки:
        # dict где ключ = (code_name, is_multiple),
        # значение = список (т.к. может быть несколько BotSettingValue)
        grouped_data = {}

        for row in rows:
            # code_name может быть enum, возьмём row.code_name.value (если enum)
            # или просто str(row.code_name). Ниже попробуем безопасно извлечь строку:
            if hasattr(row.code_name, "value"):
                code_name_str = row.code_name.value
            else:
                code_name_str = str(row.code_name)

            is_multiple = row.is_multiple
            # Определим текущее "сырое" значение:
            if row.stype == BotSettingType.boolean:
                raw_value = row.bval
            elif row.stype == BotSettingType.integer:
                raw_value = row.ival
            elif row.stype == BotSettingType.string:
                raw_value = row.str_value
            elif row.stype == BotSettingType.time_span:
                raw_value = row.time_span_value
            elif row.stype == BotSettingType.time_range:
                raw_value = row.time_range_value
            elif row.stype == BotSettingType.train_lvl:
                raw_value = row.train_lvl_value
            else:
                raw_value = None  # или обработать иные случаи

            # Сохраним в grouped_data
            # Ключ делаем простым: code_name_str
            # Но хранить и is_multiple тоже нужно (для финальной логики),
            # Можно сделать так:
            if code_name_str not in grouped_data:
                grouped_data[code_name_str] = {
                    "is_multiple": is_multiple,
                    "values": []
                }
            if raw_value is not None:
                grouped_data[code_name_str]["values"].append(raw_value)

        # Теперь формируем итоговый dict.
        # Если is_multiple = True, оставляем список,
        # если is_multiple = False, оставляем только "первое" (или последнее) значение.
        result: Dict[str, Any] = {}

        for code_name_str, data in grouped_data.items():
            is_mult = data["is_multiple"]
            vals_list = data["values"]

            if is_mult:
                # Возвращаем список (даже если 1 значение)
                result[code_name_str] = vals_list if vals_list else []
            else:
                # Вернём одно значение (если вдруг несколько,
                # можно взять первое, или последнее — зависит от бизнес-логики).
                if len(vals_list) > 0:
                    result[code_name_str] = vals_list[0]
                else:
                    # Возможно, настройка существует, но нет значений (редкий случай)
                    result[code_name_str] = None

        return result

    # TODO Заменить имя метода
    def fill_defaults_for_account(self, character_id: uuid.UUID) -> None:
        """
        Заполняет таблицы bot_setting и bot_setting_value для данного account_id,
        используя дефолтные значения из setting_default_value для каждой setting_definition.

        Логика (упрощённая):
        1) Получаем все SettingDefinition (+ default-значения, + тип).
        2) Для каждой setting_definition проверяем, есть ли BotSetting (account+definition).
            Если нет, создаём.
        3) Если у BotSetting нет записей в BotSettingValue, тогда
            - если is_multiple=False, берём первую запись из setting_default_values
            - если is_multiple=True, берём все записи из setting_default_values
            - создаём соответствующие BotSettingValue (bool/int/строковые/и т.д.).
        """

        # 1) Грузим все SettingDefinition'ы вместе с их default-значениями и (опционально) типами
        definitions = (
            self.session.query(SettingDefinition)
            .options(
                subqueryload(SettingDefinition.setting_default_values),
                joinedload(SettingDefinition.setting_type),
            )
            .all()
        )

        # 2) Для ускорения доступа, загрузим все BotSetting для этого аккаунта
        existing_bot_settings = (
            self.session.query(BotSetting)
            .filter(BotSetting.character_id == character_id)
            .all()
        )
        # Кэшируем их в dict: { (definition_id): BotSetting }
        bot_setting_map = {
            bs.setting_definition_id: bs for bs in existing_bot_settings
        }

        for definition in definitions:
            # 2a) Проверяем, есть ли уже BotSetting
            bot_setting = bot_setting_map.get(definition.id)
            if not bot_setting:
                # Создаём новую запись BotSetting
                bot_setting = BotSetting(
                    character_id=character_id,
                    setting_definition_id=definition.id
                )
                self.session.add(bot_setting)
                self.session.flush()
                bot_setting_map[definition.id] = bot_setting

            # 2b) Есть ли у этого BotSetting какие-нибудь BotSettingValue?
            if bot_setting.bot_setting_values:
                # Предположим, мы НЕ перезаписываем существующие настройки
                continue

            # 3) Создаём значения на основе default'ов
            default_values = definition.setting_default_values
            if not default_values:
                # У этой настройки нет дефолтов — пропускаем
                continue

            if definition.is_multiple:
                # Создать все default-записи
                for dval in default_values:
                    self._create_value_from_default(bot_setting, definition, dval)
            else:
                # is_multiple=False -> берём первую (или последнюю) default
                first_default = default_values[0]
                self._create_value_from_default(bot_setting, definition, first_default)

    def _create_value_from_default(
        self,
        bot_setting: BotSetting,
        definition,
        default_obj: SettingDefaultValue,
    ):
        """
        Вспомогательный метод: создать одну запись BotSettingValue из default_obj.
        Запись связывается с bot_setting.
        """
        # Узнаём тип настройки (BotSettingType)
        # У вас в SettingType хранится enum BotSettingType.*
        # или строка, которую нужно сопоставить enum. Предположим, что:
        setting_type = definition.setting_type.setting_type_name  # enum-значение

        bsv = BotSettingValue(
            bot_setting_id=bot_setting.id,
            setting_type=setting_type,
        )

        if setting_type == BotSettingType.integer:
            bsv.int_value = default_obj.default_int
        elif setting_type == BotSettingType.boolean:
            bsv.bool_value = default_obj.default_bool
        elif setting_type == BotSettingType.string:
            bsv.setting_string_value_id = default_obj.setting_string_value_id
        elif setting_type == BotSettingType.time_span:
            bsv.setting_time_span_value_id = default_obj.setting_string_value_id
        elif setting_type == BotSettingType.time_range:
            bsv.time_range_value = default_obj.default_time_range_value
        elif setting_type == BotSettingType.train_lvl:
            bsv.train_lvl_value = default_obj.default_train_lvl_value
        else:
            pass  # На всякий случай

        self.session.add(bsv)
        # commit() не делаем — сервис вызовет при выходе из транзакции


# Репозиторий для модели BotSettingValue
class BotSettingValueRepository(BaseRepository[BotSettingValue]):
    def __init__(self, session: Session):
        super().__init__(session, BotSettingValue)


# Репозиторий для модели SettingConstraint
class SettingConstraintRepository(BaseRepository[SettingConstraint]):
    def __init__(self, session: Session):
        super().__init__(session, SettingConstraint)


# Репозиторий для модели SettingConstraintStringValue
class SettingConstraintStringValueRepository(BaseRepository[SettingConstraintStringValue]):
    def __init__(self, session: Session):
        super().__init__(session, SettingConstraintStringValue)


# Репозиторий для модели SettingDefaultValue
class SettingDefaultValueRepository(BaseRepository[SettingDefaultValue]):
    def __init__(self, session: Session):
        super().__init__(session, SettingDefaultValue)


# Репозиторий для модели Question
class QuestionRepository(BaseRepository[Question]):
    def __init__(self, session: Session):
        super().__init__(session, Question)

    def get_correct_answer(self, question_text: str) -> Optional[int]:
        """
        Получает номер правильного ответа по тексту вопроса.

        :param question_text: Текст вопроса.
        :return: Номер правильного ответа или None, если вопрос не найден.
        """
        try:
            question = self.session.query(Question).filter_by(question_text=question_text).one()
            return question.answer_number
        except NoResultFound:
            return None


# Репозиторий для модели DailySettingDefinition
class DailySettingDefinitionRepository(BaseRepository[DailySettingDefinition]):
    def __init__(self, session: Session):
        super().__init__(session, DailySettingDefinition)

    def get_by_code_name_str(self, code_name_str: str) -> Optional[DailySettingDefinition]:
        """
        Ищет DailySettingDefinition по строковому имени code_name (пример: "arena_tokens").
        """
        # Обратите внимание: в модели code_name хранится как enum BotDailySettingCodename.
        # Поэтому нужно сравнивать со значением enum, например BotDailySettingCodename.arena_tokens.
        # Можно сделать через cast на текст:
        return (
            self.session.query(DailySettingDefinition)
            .filter(
                cast(DailySettingDefinition.code_name, String) == code_name_str
            )
            .one_or_none()
        )


# Репозиторий для модели BotDailySetting
class BotDailySettingRepository(BaseRepository[BotDailySetting]):
    def __init__(self, session: Session):
        super().__init__(session, BotDailySetting)

    # TODO Заменить имя метода
    def get_all_by_account(self, character_id: uuid.UUID) -> List[BotDailySetting]:
        """
        Возвращает все BotDailySetting для конкретного account_id
        вместе с SettingDefinition, SettingType и BotDailySettingValue.
        """
        result = (
            self.session.query(BotDailySetting)
            .options(
                joinedload(BotDailySetting.setting_definition)
                .joinedload(DailySettingDefinition.setting_type),
                joinedload(BotDailySetting.bot_daily_setting_values)
                .joinedload(BotDailySettingValue.setting_string_value),
            )
            .filter(BotDailySetting.character_id == character_id)
            .all()
        )
        return result

    def get_default_values_for_definitions(
        self,
        definition_ids: List[int]
    ) -> Dict[int, List[DailySettingDefaultValue]]:
        """
        Возвращает словарь, где ключ — setting_definition_id,
        а значение — список DailySettingDefaultValue для этих определений.
        """
        default_values = (
            self.session.query(DailySettingDefaultValue)
            .filter(DailySettingDefaultValue.setting_definition_id.in_(definition_ids))
            .all()
        )

        dv_map: Dict[int, List[DailySettingDefaultValue]] = {}
        for dv in default_values:
            dv_map.setdefault(dv.setting_definition_id, []).append(dv)
        return dv_map

    def get_all_definitions(self) -> List[DailySettingDefinition]:
        """
        Получает все DailySettingDefinition с предзагрузкой SettingType.
        """
        return (
            self.session.query(DailySettingDefinition)
            .options(joinedload(DailySettingDefinition.setting_type))
            .all()
        )

    def get_existing_setting_definition_ids(self, character_id: uuid.UUID) -> Set[int]:
        """
        Возвращает набор идентификаторов setting_definition_id для данного account_id.
        """
        result = (
            self.session.query(BotDailySetting.setting_definition_id)
            .filter_by(character_id=character_id)
            .all()
        )
        return {id_ for (id_,) in result}

    def get_daily_setting_by_account_and_definition(
        self,
        character_id: uuid.UUID,
        definition_id: int
    ) -> Optional[BotDailySetting]:
        """
        Ищет одну запись BotDailySetting для данного account_id и definition_id.
        """
        return (
            self.session.query(BotDailySetting)
            .filter(
                BotDailySetting.character_id == character_id,
                BotDailySetting.setting_definition_id == definition_id
            )
            .one_or_none()
        )

    def create_bot_daily_setting(
        self,
        character_id: uuid.UUID,
        definition_id: int
    ) -> BotDailySetting:
        """
        Создаёт и сохраняет BotDailySetting для указанного аккаунта
        и определения настройки.
        """
        bot_daily_setting = BotDailySetting(
            character_id=character_id,
            setting_definition_id=definition_id
        )
        self.session.add(bot_daily_setting)
        self.session.flush()  # чтобы ID уже был доступен
        return bot_daily_setting

    def create_value_from_default(
        self,
        bot_daily_setting_id: uuid.UUID,
        setting_type: BotSettingType,
        default_obj: DailySettingDefaultValue
    ) -> BotDailySettingValue:
        """
        Создаёт BotDailySettingValue на основе DailySettingDefaultValue.
        """
        bds_val = BotDailySettingValue(
            bot_daily_setting_id=bot_daily_setting_id,
            setting_type=setting_type,
        )

        # Перенос значений из default_obj в BotDailySettingValue
        if setting_type == BotSettingType.integer:
            bds_val.int_value = default_obj.default_int
        elif setting_type == BotSettingType.boolean:
            bds_val.bool_value = default_obj.default_bool
        elif setting_type in (BotSettingType.string, BotSettingType.time_span):
            bds_val.setting_string_value_id = default_obj.setting_string_value_id

        self.session.add(bds_val)
        return bds_val

    def delete_values_for_setting(self, bot_daily_setting_id: uuid.UUID) -> None:
        """
        Удаляет все BotDailySettingValue для заданного daily_setting.
        """
        (
            self.session.query(BotDailySettingValue)
            .filter(BotDailySettingValue.bot_daily_setting_id == bot_daily_setting_id)
            .delete(synchronize_session=False)
        )


# Репозиторий для модели BotDailySettingValue
class BotDailySettingValueRepository(BaseRepository[BotDailySettingValue]):
    def __init__(self, session: Session):
        super().__init__(session, BotDailySettingValue)


# Репозиторий для модели DailySettingDefinition
class DailySettingDefaultValueRepository(BaseRepository[DailySettingDefaultValue]):
    def __init__(self, session: Session):
        super().__init__(session, DailySettingDefaultValue)


# Репозиторий для модели Translation
class TranslationRepository(BaseRepository[Translation]):
    def __init__(self, session: Session):
        super().__init__(session, Translation)
