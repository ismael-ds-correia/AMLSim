from typing import List, Optional
from pydantic import BaseModel, Field, FilePath, root_validator
from typing_extensions import Literal


class StrictBaseModel(BaseModel):
    class Config:
        extra = "forbid"


class SimulationConfig(StrictBaseModel):
    total_steps: int = Field(..., gt=0)
    seed: int
    output_dir: str = Field(..., min_length=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AccountsConfig(StrictBaseModel):
    num_accounts: int = Field(..., gt=0)
    initial_balance_min: float = Field(..., ge=0)
    initial_balance_max: float = Field(..., ge=0)

    @root_validator(skip_on_failure=True)
    def check_balance_range(cls, values):
        min_balance = values.get("initial_balance_min")
        max_balance = values.get("initial_balance_max")
        if min_balance is not None and max_balance is not None and max_balance < min_balance:
            raise ValueError("initial_balance_max must be greater than or equal to initial_balance_min")
        return values


class TypologyConfig(StrictBaseModel):
    name: Literal["fragmented_deposit", "fragmented_withdrawal"]
    min_day: int = Field(..., ge=0)
    max_day: int = Field(..., ge=0)
    min_amount: float = Field(..., ge=0)
    max_amount: float = Field(..., ge=0)

    @root_validator(skip_on_failure=True)
    def check_typology_ranges(cls, values):
        min_day = values.get("min_day")
        max_day = values.get("max_day")
        min_amount = values.get("min_amount")
        max_amount = values.get("max_amount")
        if min_day is not None and max_day is not None and max_day < min_day:
            raise ValueError("max_day must be greater than or equal to min_day")
        if min_amount is not None and max_amount is not None and max_amount < min_amount:
            raise ValueError("max_amount must be greater than or equal to min_amount")
        return values


class TransactionsConfig(StrictBaseModel):
    min_amount: float = Field(..., ge=0)
    max_amount: float = Field(..., ge=0)
    typologies: List[TypologyConfig]
    LEGAL_LIMIT: float = Field(..., gt=0)
    MAX_TOTAL: float = Field(..., gt=0)
    minCycles: int = Field(..., gt=0)
    maxCycles: int = Field(..., gt=0)
    minFrac: float = Field(..., gt=0)
    maxFrac: float = Field(..., gt=0)

    @root_validator(skip_on_failure=True)
    def check_transaction_ranges(cls, values):
        min_amount = values.get("min_amount")
        max_amount = values.get("max_amount")
        min_cycles = values.get("minCycles")
        max_cycles = values.get("maxCycles")
        min_frac = values.get("minFrac")
        max_frac = values.get("maxFrac")
        if min_amount is not None and max_amount is not None and max_amount < min_amount:
            raise ValueError("max_amount must be greater than or equal to min_amount")
        if min_cycles is not None and max_cycles is not None and max_cycles < min_cycles:
            raise ValueError("maxCycles must be greater than or equal to minCycles")
        if min_frac is not None and max_frac is not None and max_frac < min_frac:
            raise ValueError("maxFrac must be greater than or equal to minFrac")
        return values



class BiasCommonConfig(StrictBaseModel):
    method: Literal["group_size", "prevalency_disparity"]
    n_ramos: int = Field(..., gt=0)
    seed: int


class GroupSizeBiasConfig(StrictBaseModel):
    target_ramo: List[int]
    v: float = Field(..., ge=0, le=1)


class PrevalencyDisparityBiasConfig(StrictBaseModel):
    g_priv: List[int]
    g_despriv: List[int]
    v_priv: float = Field(..., ge=0, le=1)
    v_despriv: float = Field(..., ge=0, le=1)


class BiasConfig(StrictBaseModel):
    common: BiasCommonConfig
    group_size: Optional[GroupSizeBiasConfig] = None
    prevalency_disparity: Optional[PrevalencyDisparityBiasConfig] = None

    @root_validator(skip_on_failure=True)
    def check_bias_blocks(cls, values):
        common = values.get("common")
        group_size = values.get("group_size")
        prevalency = values.get("prevalency_disparity")

        if common is None:
            raise ValueError("bias.common is required")

        if common.method == "group_size":
            if group_size is None:
                raise ValueError("bias.group_size block is required when bias.common.method is 'group_size'")
            # validate target ranges
            for ramo in group_size.target_ramo:
                if ramo < 1 or ramo > common.n_ramos:
                    raise ValueError(f"Each target_ramo must be within 1..{common.n_ramos}")

        elif common.method == "prevalency_disparity":
            if prevalency is None:
                raise ValueError("bias.prevalency_disparity block is required when bias.common.method is 'prevalency_disparity'")
            g_priv_set = set(prevalency.g_priv)
            g_despriv_set = set(prevalency.g_despriv)
            if not g_priv_set:
                raise ValueError("g_priv must not be empty")
            if not g_despriv_set:
                raise ValueError("g_despriv must not be empty")
            if g_priv_set.intersection(g_despriv_set):
                raise ValueError("g_priv and g_despriv must not overlap")
            for ramo in g_priv_set.union(g_despriv_set):
                if ramo < 1 or ramo > common.n_ramos:
                    raise ValueError(f"Group values must be within 1..{common.n_ramos}")

        return values


class FilesConfig(StrictBaseModel):
    param_dir: str = Field(..., min_length=1)
    schema_file: FilePath
    alert_patterns_file: FilePath
    transaction_types_file: FilePath
    output_file: Optional[str] = None


class AMLSimConfig(StrictBaseModel):
    simulation: SimulationConfig
    accounts: AccountsConfig
    transactions: TransactionsConfig
    bias: BiasConfig
    files: FilesConfig
