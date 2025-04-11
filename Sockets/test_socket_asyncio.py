import asyncio
import unittest
# Use a dot (.) before the module name for relative import
from .socket_asyncio import main

class TestSocketAsyncio(unittest.TestCase):
    def test_main_runs(self):
        """Test that the main function runs without raising any exceptions.
           We run it with a short duration (2 seconds) for faster testing."""
        try:
            # Run the main function for a short duration
            # Use nest_asyncio in case the test runner already has an event loop
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(main(duration=2))
        except Exception as e:
            self.fail(f"main() raised an exception: {e}")

if __name__ == '__main__':
    unittest.main()
