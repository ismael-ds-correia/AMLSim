from pydantic import BaseModel, Field, DirectoryPath, FilePath, conint, confloat
from typing import List, Literal, Optional

class TypologyConfig(BaseModel):
    name: str
    min_day: int = Field(..., ge=0)
    max_day: int = Field(..., ge=0)
    min_amount: float = Field(..., ge=0)
    max_amount: float = Field(..., ge=0)

class AccountsConfig(BaseModel):
    num_accounts: int = Field(..., gt=0)
    initial_balance_min: float = Field(..., ge=0)
    initial_balance_max: float = Field(..., ge=0)
    account_types: List[str]

class TransactionsConfig(BaseModel):
    min_amount: float = Field(..., ge=0)
    max_amount: float = Field(..., ge=0)
    typologies: List[TypologyConfig]

class BiasConfig(BaseModel):
    v: float = Field(..., ge=0, le=1)
    method: Literal['group_size', 'empirical']

class FilesConfig(BaseModel):
    param_dir: DirectoryPath
    schema_file: FilePath
    alert_patterns_file: FilePath
    transaction_types_file: FilePath

class SimulationConfig(BaseModel):
    total_steps: int = Field(..., gt=0)
    seed: Optional[int] = None
    output_dir: DirectoryPath
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

class AMLSimConfig(BaseModel):
    simulation: SimulationConfig
    accounts: AccountsConfig
    transactions: TransactionsConfig
    assignments: BiasConfig
    files: FilesConfig
