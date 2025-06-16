# DBmodels.py
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    BigInteger,
    Boolean,
    ForeignKey,
    Numeric,
    Interval,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import UUID, ENUM as PGEnum
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


# Определение ENUM типов, соответствующих PostgreSQL ENUM
class BotSettingCodename(enum.Enum):
    action_point_threshold = "action_point_threshold"
    alliance_res = "alliance_res"
    arsenal_make_mode = "arsenal_make_mode"
    arsenal_material_speed_up = 'arsenal_material_speed_up'
    arena_tokens = 'arena_tokens'
    arena_tokens_conquest = 'arena_tokens_conquest'
    bank_deposit_type = "bank_deposit_type"
    build_upgrade_priority = "build_upgrade_priority"
    company_bliz = "company_bliz"
    company_level = "company_level"
    company_main_challenge = "company_main_challenge"
    company_prison_level = "company_prison_level"
    company_sublevel = "company_sublevel"
    company_super_level = "company_super_level"
    group_fight_count = "group_fight_count"
    group_fight_min_lvl = "group_fight_min_lvl"
    group_fight_type_count = "group_fight_type_count"
    heal_count = "heal_count"
    heal_timer = "heal_timer"
    heal_wait_timer = "heal_wait_timer"
    hole_peaceful_mode = "hole_peaceful_mode"
    hole_min_percent = "hole_min_percent"
    hole_target_lvl = "hole_target_lvl"
    lair_lvl = "lair_lvl"
    lair_time = "lair_time"
    lang = "lang"
    map_main_resource_type = "map_main_resource_type"
    map_resource_allow_wasteland = "map_resource_allow_wasteland"
    map_resource_start_lvl = "map_resource_start_lvl"
    map_resource_types = "map_resource_types"
    map_speed_up = "map_speed_up"
    march_max_count = "march_max_count"
    march_recall_gem_usage = "march_recall_gem_usage"
    nova_priority = "nova_priority"
    over_power_arena_fight = 'over_power_arena_fight'
    sience_sectors = "sience_sectors"
    stamina_threshold = "stamina_threshold"
    store_permit = "store_permit"
    supply_diamonds_count = "supply_diamonds_count"
    supply_priority = "supply_priority"
    train_daily = "train_daily"
    train_type = "train_type"
    train_unit_types = "train_unit_types"
    unit_type = "unit_type"
    serum_limit_ignore = "serum_limit_ignore"
    sr_tile_speed_up = "sr_tile_speed_up"
    sr_tile_speed_up_buy = "sr_tile_speed_up_buy"
    war_shield_activate = "war_shield_activate"
    war_diamond_shield = "war_diamond_shield"
    war_teleport_activate = "war_teleport_activate"
    war_teleport_nearest = "war_teleport_nearest"
    ignor_states = 'ignor_states'
    rare_metal_item_list = 'rare_metal_item_list'
    rare_metal_store_mode = 'rare_metal_store_mode'
    ruin_item_list = 'ruin_item_list'
    ruin_store_mode = 'ruin_store_mode'
    boost_for_buy = 'boost_for_buy'
    auto_shield_mode = 'auto_shield_mode'
    arena_unit_type = 'arena_unit_type'
    lair_join_unit_type = 'lair_join_unit_type'
    lair_create_unit_type = 'lair_create_unit_type'
    hole_unit_type = 'hole_unit_type'


class BotDailySettingCodename(enum.Enum):
    train_daily = "train_daily"
    company_main_challenge = "company_main_challenge"
    map_resource_type = "map_resource_type"
    arsenal_daily = "arsenal_daily"
    arena_daily = "arena_daily"
    arena_tokens = 'arena_tokens'
    arena_tokens_conquest = 'arena_tokens_conquest'
    arsenal_material_speed_up = 'arsenal_material_speed_up'
    rare_metal_store = 'rare_metal_store'
    ruins_store = 'ruins_store'
    alliance_store = 'alliance_store'
    upgrade_hero = 'upgrade_hero'
    upgrade_gear = 'upgrade_gear'


class BotSettingType(enum.Enum):
    string = "string"
    integer = "integer"
    boolean = "boolean"
    time_span = "time_span"
    time_range = "time_range"
    train_lvl = "train_lvl"


class GameName(enum.Enum):
    nan = "nan"
    pns = "pns"


bot_setting_codename_enum = PGEnum(
    BotSettingCodename,
    name='bot_setting_codename',
    schema='public',
    create_type=False
)

bot_daily_setting_codename_enum = PGEnum(
    BotDailySettingCodename,
    name='bot_daily_setting_codename',
    schema='public',
    create_type=False
)

bot_setting_type_enum = PGEnum(
    BotSettingType,
    name='bot_setting_type',
    schema='public',
    create_type=False
)

game_name_enum = PGEnum(
    GameName,
    name='game_name',
    schema='public',
    create_type=False
)


# Основные Таблицы
class EFMigrationsHistory(Base):
    __tablename__ = "__EFMigrationsHistory"

    MigrationId = Column(String(150), primary_key=True)
    ProductVersion = Column(String(32), nullable=False)


class Game(Base):
    __tablename__ = "game"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_name = Column(game_name_enum, nullable=False)

    setting_groups = relationship("SettingGroup", back_populates="game", cascade="all, delete")
    game_accounts = relationship("GameAccount", back_populates="game", cascade="all, delete")
    setting_string_values = relationship("SettingStringValue", back_populates="game", cascade="all, delete")
    subs_durations = relationship("SubsDuration", back_populates="game", cascade="all, delete")


class SettingType(Base):
    __tablename__ = "setting_type"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_type_name = Column(bot_setting_type_enum, nullable=False)

    setting_definitions = relationship("SettingDefinition", back_populates="setting_type", cascade="all, delete")
    daily_setting_definitions = relationship("DailySettingDefinition", back_populates="setting_type", cascade="all, delete")


class Translation(Base):
    __tablename__ = "translation"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    resource_key = Column(Text, nullable=False)
    language_code = Column(Text, nullable=False)
    translation_value = Column(Text, nullable=True)


class ZeonUser(Base):
    __tablename__ = "zeon_user"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    telegram_id = Column(BigInteger, nullable=False)
    user_name = Column(String(50), nullable=False)
    hash_password = Column(Text, nullable=False)
    email = Column(String(100), nullable=False)
    confirmed = Column(Boolean, nullable=False)
    salt = Column(Text, nullable=False, default='')
    token_expiry_time = Column(TIMESTAMP(timezone=True), nullable=True)
    subscripted_for_logger = Column(Boolean, nullable=False, default=False)
    cost_policy = Column(Text, nullable=False)
    lang = Column(Text, nullable=False)

    game_accounts = relationship("GameAccount", back_populates="zeon_user", cascade="all, delete")


class GameAccount(Base):
    __tablename__ = "game_account"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    game_account_name = Column(String(50), nullable=False, index=True)
    zeon_user_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.zeon_user.id', ondelete='CASCADE'), nullable=True, index=True)
    game_id = Column(Integer, ForeignKey('gamebot.game.id', ondelete='CASCADE'), nullable=False, default=1)
    subscription_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    is_run = Column(Boolean, nullable=False, default=False)

    # Связь "многие-к-одному" c Game и ZeonUser
    zeon_user = relationship("ZeonUser", back_populates="game_accounts")
    game = relationship("Game", back_populates="game_accounts")

    # Связь "один-к-одному" с Emulator
    emulator = relationship("Emulator", uselist=False, back_populates="game_account", cascade="all, delete-orphan")

    # Связь "один-ко-многим" с BotSetting
    characters = relationship("Character", back_populates="game_account", cascade="all, delete")


class SettingGroup(Base):
    __tablename__ = "setting_group"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_name = Column(String(50), nullable=False)
    order = Column(Integer, nullable=False, default=0)
    game_id = Column(Integer, ForeignKey('gamebot.game.id', ondelete='CASCADE'), nullable=False)

    game = relationship("Game", back_populates="setting_groups")
    setting_definitions = relationship("SettingDefinition", back_populates="setting_group", cascade="all, delete")


class SettingStringValue(Base):
    __tablename__ = "setting_string_value"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    value = Column(String(50), nullable=False)
    game_id = Column(Integer, ForeignKey('gamebot.game.id', ondelete='RESTRICT'), nullable=False, index=True)

    game = relationship("Game", back_populates="setting_string_values")
    setting_constraint_string_values = relationship("SettingConstraintStringValue", back_populates="setting_string_value", cascade="all, delete")
    setting_default_values = relationship("SettingDefaultValue", back_populates="setting_string_value")
    normal_bsv = relationship(
        "BotSettingValue",
        back_populates="setting_string_value",
        foreign_keys="BotSettingValue.setting_string_value_id"
    )
    timespan_bsv = relationship(
        "BotSettingValue",
        back_populates="setting_time_span_value",
        foreign_keys="BotSettingValue.setting_time_span_value_id"
    )
    bot_daily_setting_values = relationship("BotDailySettingValue", back_populates="setting_string_value", cascade="all, delete")
    daily_setting_default_values = relationship("DailySettingDefaultValue", back_populates="setting_string_value", cascade="all, delete")


class SubsDuration(Base):
    __tablename__ = "subs_duration"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('gamebot.game.id', ondelete='CASCADE'), nullable=False, index=True)
    duration = Column(Interval, nullable=False)
    usdt_cost = Column(Numeric, nullable=False)
    ru_star_cost = Column(Integer, nullable=False, default=0)
    en_star_cost = Column(Integer, nullable=False, default=0)

    game = relationship("Game", back_populates="subs_durations")


class Emulator(Base):
    __tablename__ = "emulator"
    __table_args__ = {'schema': 'gamebot'}

    game_account_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.game_account.id', ondelete='CASCADE'), primary_key=True, nullable=False)
    emulator_name = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    last_launch = Column(TIMESTAMP(timezone=True), nullable=True)
    vm_id = Column(String(100), nullable=False)

    game_account = relationship("GameAccount", back_populates="emulator")


class Character(Base):
    __tablename__ = "character"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    game_account_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.game_account.id', ondelete='CASCADE'), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_on = Column(Boolean, nullable=False, default=False)
    character_panel_screen = Column(Text, nullable=False, default='')
    level = Column(Integer, nullable=False, default=0)
    position_number = Column(Integer, nullable=False, default=0)

    game_account = relationship("GameAccount", back_populates="characters")
    bot_settings = relationship("BotSetting", back_populates="character", cascade="all, delete")
    bot_daily_settings = relationship("BotDailySetting", back_populates="character", cascade="all, delete")


class SettingDefinition(Base):
    __tablename__ = "setting_definition"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_name = Column(bot_setting_codename_enum, nullable=False)
    type_id = Column(Integer, ForeignKey('gamebot.setting_type.id', ondelete='CASCADE'), nullable=False, index=True)
    is_multiple = Column(Boolean, nullable=False, default=False)
    setting_group_id = Column(Integer, ForeignKey('gamebot.setting_group.id', ondelete='CASCADE'), nullable=False, index=True)
    is_nullable = Column(Boolean, nullable=False, default=False)

    setting_type = relationship("SettingType", back_populates="setting_definitions")
    setting_group = relationship("SettingGroup", back_populates="setting_definitions")
    bot_settings = relationship("BotSetting", back_populates="setting_definition", cascade="all, delete")
    setting_constraints = relationship("SettingConstraint", back_populates="setting_definition", cascade="all, delete")
    setting_default_values = relationship("SettingDefaultValue", back_populates="setting_definition", cascade="all, delete")


class BotSetting(Base):
    __tablename__ = "bot_setting"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    character_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.character.id', ondelete='CASCADE'), nullable=False, index=True)
    setting_definition_id = Column(Integer, ForeignKey("gamebot.setting_definition.id", ondelete="CASCADE"), nullable=False, index=True)

    character = relationship("Character", back_populates="bot_settings")
    setting_definition = relationship("SettingDefinition", back_populates="bot_settings")
    bot_setting_values = relationship("BotSettingValue", back_populates="bot_setting", cascade="all, delete")


class BotSettingValue(Base):
    __tablename__ = "bot_setting_value"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    bot_setting_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.bot_setting.id', ondelete='CASCADE'), nullable=False, index=True)
    setting_type = Column(bot_setting_type_enum, nullable=False)
    bool_value = Column(Boolean, nullable=True)
    int_value = Column(Integer, nullable=True)
    setting_string_value_id = Column(Integer, ForeignKey("gamebot.setting_string_value.id", ondelete="RESTRICT"), nullable=True, index=True)
    setting_time_span_value_id = Column(Integer, ForeignKey("gamebot.setting_string_value.id", ondelete="CASCADE"), nullable=True, index=True)
    time_range_value = Column(String(32), nullable=True)
    train_lvl_value = Column(String(32), nullable=True)

    bot_setting = relationship("BotSetting", back_populates="bot_setting_values")
    setting_string_value = relationship(
        "SettingStringValue",
        foreign_keys=[setting_string_value_id],
        back_populates="normal_bsv"
    )
    setting_time_span_value = relationship(
        "SettingStringValue",
        foreign_keys=[setting_time_span_value_id],
        back_populates="timespan_bsv"
    )


class SettingConstraint(Base):
    __tablename__ = "setting_constraint"
    __table_args__ = {'schema': 'gamebot'}

    setting_definition_id = Column(Integer, ForeignKey("gamebot.setting_definition.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    min_int = Column(Integer, nullable=True)
    max_int = Column(Integer, nullable=True)

    setting_definition = relationship("SettingDefinition", back_populates="setting_constraints")
    setting_constraint_string_values = relationship("SettingConstraintStringValue", back_populates="setting_constraint", cascade="all, delete")


class SettingConstraintStringValue(Base):
    __tablename__ = "setting_constraint_string_value"
    __table_args__ = {'schema': 'gamebot'}

    setting_constraint_id = Column(
        Integer,
        ForeignKey('gamebot.setting_constraint.setting_definition_id', ondelete='CASCADE'),
        primary_key=True,  # Установлено как первичный ключ
        nullable=False
    )
    setting_string_value_id = Column(
        Integer,
        ForeignKey('gamebot.setting_string_value.id', ondelete='CASCADE'),
        primary_key=True,  # Установлено как первичный ключ
        nullable=False
    )

    setting_constraint = relationship("SettingConstraint", back_populates="setting_constraint_string_values")
    setting_string_value = relationship("SettingStringValue", back_populates="setting_constraint_string_values")


class SettingDefaultValue(Base):
    __tablename__ = "setting_default_value"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_definition_id = Column(Integer, ForeignKey("gamebot.setting_definition.id", ondelete="CASCADE"), nullable=False, index=True)
    default_int = Column(Integer, nullable=True)
    default_bool = Column(Boolean, nullable=True)
    setting_string_value_id = Column(Integer, ForeignKey("gamebot.setting_string_value.id", ondelete="RESTRICT"), nullable=True, index=True)
    default_time_range_value = Column(String(32), nullable=True)
    default_train_lvl_value = Column(String(32), nullable=True)

    setting_definition = relationship("SettingDefinition", back_populates="setting_default_values")
    setting_string_value = relationship("SettingStringValue", back_populates="setting_default_values")


class DailySettingDefinition(Base):
    __tablename__ = "daily_setting_definition"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_name = Column(bot_daily_setting_codename_enum, nullable=False)
    type_id = Column(Integer, ForeignKey('gamebot.setting_type.id', ondelete='CASCADE'), nullable=False, index=True)
    is_multiple = Column(Boolean, nullable=False, default=False)

    setting_type = relationship("SettingType", back_populates="daily_setting_definitions")
    bot_daily_settings = relationship("BotDailySetting", back_populates="setting_definition", cascade="all, delete")
    daily_setting_default_values = relationship("DailySettingDefaultValue", back_populates="setting_definition", cascade="all, delete")


class BotDailySetting(Base):
    __tablename__ = "bot_daily_setting"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    character_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.character.id', ondelete='CASCADE'), nullable=False, index=True)
    setting_definition_id = Column(Integer, ForeignKey("gamebot.daily_setting_definition.id", ondelete="CASCADE"), nullable=False, index=True)
    last_update = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.now(timezone.utc))

    character = relationship("Character", back_populates="bot_daily_settings")
    setting_definition = relationship("DailySettingDefinition", back_populates="bot_daily_settings")
    bot_daily_setting_values = relationship("BotDailySettingValue", back_populates="bot_daily_setting", cascade="all, delete")


class BotDailySettingValue(Base):
    __tablename__ = "bot_daily_setting_value"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    bot_daily_setting_id = Column(UUID(as_uuid=True), ForeignKey('gamebot.bot_daily_setting.id', ondelete='CASCADE'), nullable=False, index=True)
    setting_type = Column(bot_setting_type_enum, nullable=False)
    bool_value = Column(Boolean, nullable=True)
    int_value = Column(Integer, nullable=True)
    setting_string_value_id = Column(Integer, ForeignKey("gamebot.setting_string_value.id", ondelete="RESTRICT"), nullable=True)

    bot_daily_setting = relationship("BotDailySetting", back_populates="bot_daily_setting_values")
    setting_string_value = relationship("SettingStringValue", back_populates="bot_daily_setting_values")


class DailySettingDefaultValue(Base):
    __tablename__ = "daily_setting_default_value"
    __table_args__ = {'schema': 'gamebot'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_definition_id = Column(Integer, ForeignKey("gamebot.daily_setting_definition.id", ondelete="CASCADE"), nullable=False, index=True)
    default_int = Column(Integer, nullable=True)
    default_bool = Column(Boolean, nullable=True)
    setting_string_value_id = Column(Integer, ForeignKey("gamebot.setting_string_value.id", ondelete="RESTRICT"), nullable=True, index=True)

    setting_definition = relationship("DailySettingDefinition", back_populates="daily_setting_default_values")
    setting_string_value = relationship("SettingStringValue", back_populates="daily_setting_default_values")


class Question(Base):
    __tablename__ = 'question'
    __table_args__ = {'schema': 'quiz'}

    id_question = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, nullable=False)
    question_text = Column(String, nullable=False, unique=True)
    answer_number = Column(Integer, nullable=False)
