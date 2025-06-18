# Copyright 2024 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Mapping, Tuple, Type, Union

from pydantic import AliasChoices, Field
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings.sources import parse_env_vars


class PulumiSettingsSource(EnvSettingsSource):
    """Pulumi stack outputs as a pydantic settings source."""

    _PULUMI_OUTPUTS: Dict[str, str] = {}
    _PULUMI_CALLED: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.read_pulumi_outputs()
        super().__init__(*args, **kwargs)

    def read_pulumi_outputs(self) -> None:
        try:
            raw_outputs = json.loads(
                subprocess.check_output(
                    ["pulumi", "stack", "output", "-j"],
                    text=True,
                ).strip()
            )
            self._PULUMI_OUTPUTS = {
                k: v if isinstance(v, str) else json.dumps(v)
                for k, v in raw_outputs.items()
            }
        except BaseException:
            self._PULUMI_OUTPUTS = {}

    def _load_env_vars(self) -> Mapping[str, Union[str, None]]:
        return parse_env_vars(
            self._PULUMI_OUTPUTS,
            self.case_sensitive,
            self.env_ignore_empty,
            self.env_parse_none_str,
        )


class DynamicSettings(BaseSettings):
    """Settings that come from pulumi stack outputs or DR runtime parameters"""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            PulumiSettingsSource(settings_cls),
            env_settings,
        )


app_settings_env_name: str = "ANALYST_APP_SETTINGS"

app_env_name: str = "DATAROBOT_APPLICATION_ID"

llm_deployment_env_name: str = "LLM_DEPLOYMENT_ID"


class UseCaseSettings(DynamicSettings):
    """Settings for use case filtering configuration"""
    
    use_cases: list[str] = Field(
        default_factory=list,
        description="List of use case names to filter datasets from DataRobot AI Catalog"
    )
    use_case_filter_enabled: bool = Field(
        default=True,
        description="Whether to enable use case filtering for dataset access"
    )
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            PulumiSettingsSource(settings_cls),
            env_settings,
        )


def get_use_case_config() -> dict[str, Any]:
    """Get use case configuration from multiple sources"""
    try:
        # Try to get from UseCaseSettings (environment variables, Pulumi)
        use_case_settings = UseCaseSettings()
        return {
            "use_cases": use_case_settings.use_cases,
            "use_case_filter_enabled": use_case_settings.use_case_filter_enabled
        }
    except Exception:
        # Fallback to app_infra.json
        try:
            from utils.database_helpers import load_app_infra
            app_infra = load_app_infra()
            return {
                "use_cases": getattr(app_infra, 'use_cases', []),
                "use_case_filter_enabled": getattr(app_infra, 'use_case_filter_enabled', True)
            }
        except Exception:
            # Default configuration
            return {
                "use_cases": [],
                "use_case_filter_enabled": True
            }


class LLMDeployment(DynamicSettings):
    id: str = Field(
        validation_alias=AliasChoices(
            "MLOPS_RUNTIME_PARAM_" + llm_deployment_env_name,
            llm_deployment_env_name,
        )
    )
