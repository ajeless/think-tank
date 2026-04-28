"""Compatibility facade for Think Tank configuration behavior."""

from __future__ import annotations

from .config_auth import (
    AuthAddResult,
    AuthDoctorProvider,
    AuthDoctorResult,
    AuthListResult,
    AuthProviderConfig,
    AuthRemoveResult,
    ConfigInitResult,
    ProviderAuthNotReadyError,
    add_config_auth,
    doctor_config_auth,
    list_config_auth,
    remove_config_auth,
    write_detected_provider_config,
)
from .config_common import (
    AuthMethodConfig,
    DefaultsConfig,
    ModelProfileNotFoundError,
)
from .config_defaults import (
    DefaultRemoveResult,
    DefaultsListResult,
    DefaultsSetResult,
    list_config_defaults,
    remove_config_default,
    set_config_defaults,
)
from .config_models import (
    ModelAddResult,
    ModelListResult,
    ModelProfile,
    ModelRemoveResult,
    add_model_profile,
    list_model_profiles,
    remove_model_profile,
    resolve_model_profile,
)
from .config_store import (
    ConfigFormatError,
    ConfigNotFoundError,
    default_config_path,
    load_config,
)
from .provider_registry import (
    PROVIDER_SPECS,
    ProviderAuthMethodOption,
    ProviderAuthMethodSpec,
    ProviderSpec,
    ProviderStatus,
    detect_provider_statuses,
    provider_auth_method_options,
)


__all__ = [
    "AuthAddResult",
    "AuthDoctorProvider",
    "AuthDoctorResult",
    "AuthListResult",
    "AuthMethodConfig",
    "AuthProviderConfig",
    "AuthRemoveResult",
    "ConfigFormatError",
    "ConfigInitResult",
    "ConfigNotFoundError",
    "DefaultRemoveResult",
    "DefaultsConfig",
    "DefaultsListResult",
    "DefaultsSetResult",
    "ModelAddResult",
    "ModelListResult",
    "ModelProfile",
    "ModelProfileNotFoundError",
    "ModelRemoveResult",
    "PROVIDER_SPECS",
    "ProviderAuthMethodOption",
    "ProviderAuthMethodSpec",
    "ProviderAuthNotReadyError",
    "ProviderSpec",
    "ProviderStatus",
    "add_config_auth",
    "add_model_profile",
    "default_config_path",
    "detect_provider_statuses",
    "doctor_config_auth",
    "list_config_auth",
    "list_config_defaults",
    "list_model_profiles",
    "load_config",
    "provider_auth_method_options",
    "remove_config_auth",
    "remove_config_default",
    "remove_model_profile",
    "resolve_model_profile",
    "set_config_defaults",
    "write_detected_provider_config",
]
