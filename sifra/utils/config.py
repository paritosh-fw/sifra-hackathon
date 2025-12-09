#!/usr/bin/env python3
"""
Configuration management for Sifra Advanced
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """
    Configuration manager for Sifra Advanced
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize configuration
        
        Args:
            config_path (str): Path to configuration file
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                self._config = yaml.safe_load(file)
        except FileNotFoundError:
            print(f"⚠️  Configuration file not found: {self.config_path}")
            self._config = {}
        except yaml.YAMLError as e:
            print(f"❌ Error parsing configuration file: {e}")
            self._config = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key
        
        Args:
            key (str): Configuration key (supports dot notation)
            default (Any): Default value if key not found
            
        Returns:
            Any: Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set configuration value
        
        Args:
            key (str): Configuration key (supports dot notation)
            value (Any): Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as file:
                yaml.dump(self._config, file, default_flow_style=False)
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")
    
    @property
    def llm(self) -> Dict[str, Any]:
        """Get LLM configuration"""
        return self.get('llm', {})
    
    @property
    def slack(self) -> Dict[str, Any]:
        """Get Slack configuration"""
        return self.get('slack', {})
    
    @property
    def freshdesk(self) -> Dict[str, Any]:
        """Get Freshdesk configuration"""
        return self.get('freshdesk', {})
    
    @property
    def agents(self) -> Dict[str, Any]:
        """Get agents configuration"""
        return self.get('agents', {})
    
    @property
    def tasks(self) -> Dict[str, Any]:
        """Get tasks configuration"""
        return self.get('tasks', {})
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get data paths configuration"""
        return self.get('data', {})
    
    @property
    def haystack(self) -> Dict[str, Any]:
        """Get Haystack configuration"""
        return self.get('haystack', {})
    
    @property
    def confluence(self) -> Dict[str, Any]:
        """Get Confluence configuration"""
        return self.get('confluence', {})
    
    @property
    def freshops(self) -> Dict[str, Any]:
        """Get Freshops configuration"""
        return self.get('freshops', {})