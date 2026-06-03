"""Configuration collection and validation for PDF operations.

Responsibility: Extract user inputs from UI widgets and validate them.
"""

import logging

logger = logging.getLogger(__name__)


class ConfigCollector:
    """Mixin for collecting and validating operation configuration.

    Responsibility: ONLY config collection and validation.

    Subclasses must implement _collect_config_impl() to gather values
    from UI widgets and return a config object.
    """

    def collect_config(self):
        """Collect and validate configuration.

        Returns:
            Config object if valid, None if invalid or no configuration is needed.
        """
        try:
            config = self._collect_config_impl()
            if config is not None:
                self._validate_config(config)
            return config
        except ValueError as e:
            logger.warning(f"Config validation failed: {e}")
            return None

    def _collect_config_impl(self):
        """Subclasses override this to collect config from UI widgets.

        Returns:
            Config object or None.
        """
        raise NotImplementedError

    def _validate_config(self, config) -> None:
        """Subclasses can override to validate config.

        Should raise ValueError if validation fails.

        Args:
            config: The config object to validate.
        """
        # Base implementation: no validation
        pass
