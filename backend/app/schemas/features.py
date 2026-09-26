"""Customer capability response/update schemas."""

from pydantic import BaseModel


class FeatureDecisionOut(BaseModel):
    key: str
    label: str
    allowed: bool
    release_allowed: bool
    entitlement_allowed: bool
    org_config_allowed: bool
    permission_allowed: bool
    org_configurable: bool


class MyFeaturesOut(BaseModel):
    flags: dict[str, bool]
    features: list[FeatureDecisionOut]


class FeatureSettingOut(FeatureDecisionOut):
    enabled: bool


class FeatureSettingsOut(BaseModel):
    items: list[FeatureSettingOut]


class FeatureSettingUpdateIn(BaseModel):
    enabled: bool
