# In tests, mock_config should be imported before any script that uses the
# config file. This will mock out the content of those files and allow tests to
# pass. If this file is not imported, then tests will fail with "No Module
# named 'config'" in the pipeline.

import sys
from unittest.mock import MagicMock

# Create a mock config module
mock_config = MagicMock()
mock_config.N_APIkey = "fake_neon_key"
mock_config.N_APIuser = "fake_neon_user"

# Inject it into sys.modules BEFORE importing your script
sys.modules['config'] = mock_config
