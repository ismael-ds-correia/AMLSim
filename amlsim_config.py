from typing import List

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


class BiasConfig(StrictBaseModel):
    method: Literal["group_size", "prevalency_disparity"]
    v: float = Field(..., ge=0, le=1)
    n_ramos: int = Field(..., gt=0)
    target_ramo: List[int]
    seed: int

    @root_validator(skip_on_failure=True)
    def check_bias_targets(cls, values):
        target_ramo = values.get("target_ramo") or []
        n_ramos = values.get("n_ramos")
        if not target_ramo:
            raise ValueError("target_ramo must not be empty")
        if n_ramos is not None:
            for ramo in target_ramo:
                if ramo < 1 or ramo > n_ramos:
                    raise ValueError(f"target_ramo values must be within 1..{n_ramos}")
        return values


class FilesConfig(StrictBaseModel):
    param_dir: str = Field(..., min_length=1)
    schema_file: FilePath
    alert_patterns_file: FilePath
    transaction_types_file: FilePath


class AMLSimConfig(StrictBaseModel):
    simulation: SimulationConfig
    accounts: AccountsConfig
    transactions: TransactionsConfig
    bias: BiasConfig
    files: FilesConfig
