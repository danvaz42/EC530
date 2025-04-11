# Sockets/test_socket_asyncio.py

import asyncio
import unittest
# Import assuming runner is at the project root
from Sockets.socket_asyncio import main
import nest_asyncio

nest_asyncio.apply()

class TestSocketAsyncio(unittest.TestCase):
    def test_main_runs(self):
        """Test that the main function runs without raising any exceptions.
           We run it with a short duration (2 seconds) for faster testing."""
        try:
            asyncio.run(main(duration=2))
        except Exception as e:
            self.fail(f"main() raised an exception: {e}")

if __name__ == '__main__':
    unittest.main()
