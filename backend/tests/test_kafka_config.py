import app.events.kafka as kafka_mod
from app.core.config import Settings
from app.events.kafka import client_config


def _patch_settings(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(kafka_mod, "settings", Settings())


def test_client_config_plaintext_by_default(monkeypatch):
    _patch_settings(
        monkeypatch,
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_SECURITY_PROTOCOL="PLAINTEXT",
    )
    cfg = client_config()
    assert cfg["bootstrap.servers"] == "localhost:9092"
    assert cfg["broker.address.family"] == "v4"
    assert "security.protocol" not in cfg


def test_client_config_sasl_plain(monkeypatch):
    _patch_settings(
        monkeypatch,
        KAFKA_BOOTSTRAP_SERVERS="kafka.internal:9092",
        KAFKA_SECURITY_PROTOCOL="SASL_PLAINTEXT",
        KAFKA_SASL_USERNAME="app-user",
        KAFKA_SASL_PASSWORD="super-secret",
    )
    cfg = client_config()
    assert cfg["bootstrap.servers"] == "kafka.internal:9092"
    assert cfg["broker.address.family"] == "v4"
    assert cfg["security.protocol"] == "SASL_PLAINTEXT"
    assert cfg["sasl.mechanism"] == "PLAIN"
    assert cfg["sasl.username"] == "app-user"
    assert cfg["sasl.password"] == "super-secret"


def test_client_config_extra_overrides_base(monkeypatch):
    _patch_settings(
        monkeypatch,
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_SECURITY_PROTOCOL="PLAINTEXT",
    )
    cfg = client_config({"group.id": "workers", "enable.auto.commit": False})
    assert cfg["group.id"] == "workers"
    assert cfg["enable.auto.commit"] is False


def test_client_config_address_family_override(monkeypatch):
    _patch_settings(
        monkeypatch,
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_BROKER_ADDRESS_FAMILY="any",
    )
    assert client_config()["broker.address.family"] == "any"
