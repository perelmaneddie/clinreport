from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VariantRules(BaseModel):
    min_dp: int = 10
    min_gq: int = 20
    max_gnomad_af: float = 0.01
    include_clinvar: list[str] = Field(default_factory=lambda: ["Pathogenic", "Likely_pathogenic"])
    include_consequences: list[str] = Field(
        default_factory=lambda: [
            "stop_gained",
            "frameshift_variant",
            "splice_acceptor_variant",
            "splice_donor_variant",
        ]
    )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLINREPORT_", extra="ignore")
    rules: VariantRules = VariantRules()

    bcftools_path: str = "bcftools"
    fastp_path: str = "fastp"
    igv_sh_path: str = "igv.sh"

    openai_model: str = "gpt-5"
    openai_timeout_s: int = 120


settings = AppSettings()
