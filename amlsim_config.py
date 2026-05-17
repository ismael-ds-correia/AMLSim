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


class BiasConfig(StrictBaseModel):
    method: Literal["group_size", "prevalency_disparity"]
    n: Optional[int] = Field(None, gt=0)
    n_ramos: Optional[int] = Field(None, gt=0)
    target_ramo: Optional[List[int]] = None
    g_priv: Optional[List[int]] = None
    g_despriv: Optional[List[int]] = None
    v: Optional[float] = Field(None, ge=0, le=1)
    v_priv: Optional[float] = Field(None, ge=0, le=1)
    v_despriv: Optional[float] = Field(None, ge=0, le=1)
    seed: int

    @root_validator(skip_on_failure=True)
    def check_bias_targets(cls, values):
        method = values.get("method")
        n_ramos = values.get("n") or values.get("n_ramos")
        if method == "group_size":
            target_ramo = values.get("target_ramo") or []
            v = values.get("v")
            if not target_ramo:
                raise ValueError("target_ramo must not be empty")
            if v is None:
                raise ValueError("v is required when method is group_size")
            if n_ramos is not None:
                for ramo in target_ramo:
                    if ramo < 1 or ramo > n_ramos:
                        raise ValueError(f"target_ramo values must be within 1..{n_ramos}")
        elif method == "prevalency_disparity":
            g_priv = values.get("g_priv") or []
            g_despriv = values.get("g_despriv") or []
            v_priv = values.get("v_priv")
            v_despriv = values.get("v_despriv")
            if n_ramos is None:
                raise ValueError("n is required when method is prevalency_disparity")
            if not g_priv:
                raise ValueError("g_priv must not be empty")
            if not g_despriv:
                raise ValueError("g_despriv must not be empty")
            if v_priv is None:
                raise ValueError("v_priv is required when method is prevalency_disparity")
            if v_despriv is None:
                raise ValueError("v_despriv is required when method is prevalency_disparity")
            g_priv_set = set(g_priv)
            g_despriv_set = set(g_despriv)
            overlap = g_priv_set.intersection(g_despriv_set)
            if overlap:
                raise ValueError("g_priv and g_despriv must not overlap")
            for ramo in g_priv_set.union(g_despriv_set):
                if ramo < 1 or ramo > n_ramos:
                    raise ValueError(f"Group values must be within 1..{n_ramos}")
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
