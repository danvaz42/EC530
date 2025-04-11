# Sockets/test_socket_asyncio.py

import asyncio
import unittest
# Import from 'Sockets' assuming the test runner runs from the parent directory
from Sockets.socket_asyncio import main
import nest_asyncio

# Apply nest_asyncio in case the test runner environment needs it
# It's generally safe to apply multiple times if needed.
nest_asyncio.apply()

class TestSocketAsyncio(unittest.TestCase):
    def test_main_runs(self):
        """Test that the main function runs without raising any exceptions.
           We run it with a short duration (2 seconds) for faster testing."""
        try:
            # Run the main function for a short duration
            asyncio.run(main(duration=2))
        except Exception as e:
            self.fail(f"main() raised an exception: {e}")

if __name__ == '__main__':
    # This allows running the test file directly, though discover is preferred
    unittest.main()
