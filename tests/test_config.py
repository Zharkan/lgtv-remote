import os
from pathlib import Path

from lgtv_remote.config import AppConfig, ConfigStore, TvConfig


class TestConfigStore:
    def _make_store(self, tmp_path: Path) -> ConfigStore:
        return ConfigStore(path=tmp_path / "config")

    def test_fresh_config(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.config.tvs == []
        assert store.active_tv is None

    def test_add_tv(self, tmp_path):
        store = self._make_store(tmp_path)
        tv = TvConfig.new("Living Room", "192.168.10.42", mac="f8:01:b4:a5:d8:b2")
        store.add_tv(tv)
        assert len(store.config.tvs) == 1
        assert store.active_tv == tv

    def test_round_trip(self, tmp_path):
        config_dir = tmp_path / "config"
        store = self._make_store(tmp_path)
        tv = TvConfig.new("Living Room", "192.168.10.42")
        tv.client_key = "test-key-123"
        store.add_tv(tv)

        store2 = ConfigStore(path=config_dir)
        assert len(store2.config.tvs) == 1
        loaded = store2.config.tvs[0]
        assert loaded.label == "Living Room"
        assert loaded.host == "192.168.10.42"
        assert loaded.client_key == "test-key-123"
        assert loaded.id == tv.id

    def test_file_permissions(self, tmp_path):
        store = self._make_store(tmp_path)
        store.add_tv(TvConfig.new("Test", "10.0.0.1"))
        config_file = tmp_path / "config" / "config.json"
        mode = os.stat(config_file).st_mode & 0o777
        assert mode == 0o600

    def test_remove_tv(self, tmp_path):
        store = self._make_store(tmp_path)
        tv1 = TvConfig.new("TV1", "10.0.0.1")
        tv2 = TvConfig.new("TV2", "10.0.0.2")
        store.add_tv(tv1)
        store.add_tv(tv2)
        store.remove_tv(tv1.id)
        assert len(store.config.tvs) == 1
        assert store.active_tv == tv2

    def test_update_tv(self, tmp_path):
        store = self._make_store(tmp_path)
        tv = TvConfig.new("Old", "10.0.0.1")
        store.add_tv(tv)
        tv.label = "New"
        tv.client_key = "new-key"
        store.update_tv(tv)

        store2 = ConfigStore(path=tmp_path / "config")
        assert store2.config.tvs[0].label == "New"
        assert store2.config.tvs[0].client_key == "new-key"

    def test_set_active(self, tmp_path):
        store = self._make_store(tmp_path)
        tv1 = TvConfig.new("TV1", "10.0.0.1")
        tv2 = TvConfig.new("TV2", "10.0.0.2")
        store.add_tv(tv1)
        store.add_tv(tv2)
        store.set_active(tv2.id)
        assert store.active_tv == tv2

    def test_schema_version(self, tmp_path):
        store = self._make_store(tmp_path)
        store.add_tv(TvConfig.new("Test", "10.0.0.1"))
        store2 = ConfigStore(path=tmp_path / "config")
        assert store2.config.schema_version == 2

    def test_corrupt_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text("not json")
        store = ConfigStore(path=config_dir)
        assert store.config.tvs == []
