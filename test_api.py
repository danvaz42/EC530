import os
import shutil
import unittest
import json
from api import (
    setup_environment,
    create_user, read_user, update_user, delete_user,
    create_house, read_house, update_house, delete_house,
    create_room, read_room, update_room, delete_room,
    create_device, read_device, update_device, delete_device
)

TEST_BASE_DIR = "main"

class TestAPICRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up environment before running tests
        setup_environment()

    @classmethod
    def tearDownClass(cls):
        # Cleanup the created main directory after tests
        if os.path.exists(TEST_BASE_DIR):
            shutil.rmtree(TEST_BASE_DIR)

    def test_user_crud(self):
        # Create a user
        user_id = create_user("Bob", "bob456", "555-555-5555", {"role": "user"}, "bob@example.com")
        self.assertIsNotNone(user_id, "User creation failed.")
        user_data = read_user(user_id)
        self.assertEqual(user_data["User_Name"], "Bob", "User read failed.")
        
        # Update user
        update_user(user_id, {"User_Phone": "111-111-1111"})
        user_data_updated = read_user(user_id)
        self.assertEqual(user_data_updated["User_Phone"], "111-111-1111", "User update failed.")
        
        # Delete user
        delete_user(user_id)
        self.assertIsNone(read_user(user_id), "User deletion failed.")
        print("User CRUD tests passed.")

    def test_house_crud(self):
        # Create a house
        house_id = create_house("TestHouse", "123 Test Ave", "0,0", ["user1"], [])
        self.assertIsNotNone(house_id, "House creation failed.")
        house_data = read_house(house_id)
        self.assertEqual(house_data["House_Name"], "TestHouse", "House read failed.")
        
        # Update house
        update_house(house_id, {"House_Address": "456 New Ave"})
        house_data_updated = read_house(house_id)
        self.assertEqual(house_data_updated["House_Address"], "456 New Ave", "House update failed.")
        
        # Delete house
        delete_house(house_id)
        self.assertIsNone(read_house(house_id), "House deletion failed.")
        print("House CRUD tests passed.")

    def test_room_crud(self):
        # Create a room
        # First create a dummy house to assign room to
        house_id = create_house("RoomHouse", "789 Room Rd", "1,1", ["user2"], [])
        room_id = create_room("Living Room", "1", "200 sqft", house_id, {"type": "living"})
        self.assertIsNotNone(room_id, "Room creation failed.")
        room_data = read_room(room_id)
        self.assertEqual(room_data["Room_Name"], "Living Room", "Room read failed.")
        
        # Update room
        update_room(room_id, {"Room_Size": "250 sqft"})
        room_data_updated = read_room(room_id)
        self.assertEqual(room_data_updated["Room_Size"], "250 sqft", "Room update failed.")
        
        # Delete room
        delete_room(room_id)
        self.assertIsNone(read_room(room_id), "Room deletion failed.")
        print("Room CRUD tests passed.")

    def test_device_crud(self):
        # Create a device
        # First create a dummy room to assign device to
        house_id = create_house("DeviceHouse", "321 Device Blvd", "2,2", ["user3"], [])
        room_id = create_room("Device Room", "2", "150 sqft", house_id, {"type": "bedroom"})
        device_id = create_device({"type": "sensor"}, "Test Sensor", room_id, {"sensitivity": "high"}, "data", {"status": "active"})
        self.assertIsNotNone(device_id, "Device creation failed.")
        device_data = read_device(device_id)
        self.assertEqual(device_data["Device_Name"], "Test Sensor", "Device read failed.")
        
        # Update device
        update_device(device_id, {"Device_Status": {"status": "inactive"}})
        device_data_updated = read_device(device_id)
        self.assertEqual(device_data_updated["Device_Status"]["status"], "inactive", "Device update failed.")
        
        # Delete device
        delete_device(device_id)
        self.assertIsNone(read_device(device_id), "Device deletion failed.")
        print("Device CRUD tests passed.")

if __name__ == '__main__':
    # Run the tests and output a message for pass/fail.
    result = unittest.main(verbosity=2, exit=False)
    if result.result.wasSuccessful():
        print("All tests passed!")
    else:
        print("Some tests failed!")
