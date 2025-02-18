import os
import csv
import random
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Base directory for all files
BASE_DIR = "main"

# Master CSV files to keep track of unique IDs
MASTER_FILES = {
    "User_ID": os.path.join(BASE_DIR, "User_IDs.csv"),
    "House_ID": os.path.join(BASE_DIR, "House_IDs.csv"),
    "Room_ID": os.path.join(BASE_DIR, "Room_IDs.csv"),
    "Device_ID": os.path.join(BASE_DIR, "Device_IDs.csv")
}

# Folders for individual module CSVs
MODULE_FOLDERS = {
    "User": os.path.join(BASE_DIR, "Users"),
    "House": os.path.join(BASE_DIR, "Houses"),
    "Room": os.path.join(BASE_DIR, "Rooms"),
    "Device": os.path.join(BASE_DIR, "Devices")
}

# CSV header definitions for each module
MODULE_HEADERS = {
    "User": ["User_ID", "User_Name", "User_Username", "User_Phone", "User_Privlege", "User_Email"],
    "House": ["House_ID", "House_Name", "House_Address", "House_GPS", "House_Owner", "House_Occupant"],
    "Room": ["Room_ID", "Room_Name", "Room_Floor", "Room_Size", "Room_House", "Room_Type"],
    "Device": ["Device_ID", "Device_Type", "Device_Name", "Device_Room", "Device_Settings", "Device_Data", "Device_Status"]
}

def setup_environment():
    """Sets up the main folder, master ID CSV files, and module folders."""
    try:
        if not os.path.exists(BASE_DIR):
            os.makedirs(BASE_DIR)
            logging.info("Created base directory: %s", BASE_DIR)
        
        # Create master CSV files with a header for ID tracking
        for id_key, filepath in MASTER_FILES.items():
            if not os.path.exists(filepath):
                with open(filepath, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["ID"])
                logging.info("Created master file: %s", filepath)
        
        # Create folders for each module
        for folder in MODULE_FOLDERS.values():
            if not os.path.exists(folder):
                os.makedirs(folder)
                logging.info("Created module folder: %s", folder)
    except Exception as e:
        logging.error("Error during environment setup: %s", e)

def generate_unique_ID(ID_type):
    """
    Generates a new random unique 9-digit ID for the given ID_type 
    (one of "User_ID", "House_ID", "Room_ID", or "Device_ID") and appends it to the master list.
    """
    master_file = MASTER_FILES.get(ID_type)
    if not master_file:
        raise ValueError("Invalid ID type provided.")
    
    try:
        existing_ids = set()
        with open(master_file, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                existing_ids.add(row["ID"])
        
        # Loop until a unique 9-digit ID is found
        new_id = None
        while True:
            candidate = str(random.randint(100000000, 999999999))
            if candidate not in existing_ids:
                new_id = candidate
                break

        # Append the new ID to the master CSV file
        with open(master_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([new_id])
        
        return new_id
    except Exception as e:
        logging.error("Error generating unique ID for %s: %s", ID_type, e)
        return None

# -----------------------------------------
# Helper functions for file operations
# -----------------------------------------
def write_module_csv(module, data):
    """
    Writes the data (a dictionary) into a new CSV file for the given module.
    The file is named using the unique ID (first header) and is stored in the module's folder.
    """
    try:
        folder = MODULE_FOLDERS.get(module)
        headers = MODULE_HEADERS.get(module)
        if not folder or not headers:
            raise ValueError("Invalid module provided.")
        
        filename = os.path.join(folder, data[headers[0]] + ".csv")
        with open(filename, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerow(data)
        logging.info("%s file created: %s", module, filename)
    except Exception as e:
        logging.error("Error writing %s CSV: %s", module, e)

def read_module_csv(module, unique_id):
    """
    Reads and returns the data from the CSV file for the given module and unique ID.
    """
    try:
        folder = MODULE_FOLDERS.get(module)
        headers = MODULE_HEADERS.get(module)
        filename = os.path.join(folder, unique_id + ".csv")
        if not os.path.exists(filename):
            logging.warning("%s with ID %s does not exist.", module, unique_id)
            return None
        with open(filename, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            data = next(reader)  # Only one row per file
        return data
    except Exception as e:
        logging.error("Error reading %s CSV with ID %s: %s", module, unique_id, e)
        return None

def update_module_csv(module, unique_id, updated_data):
    """
    Updates the CSV file for the given module and unique ID with the provided updated_data.
    """
    try:
        folder = MODULE_FOLDERS.get(module)
        headers = MODULE_HEADERS.get(module)
        filename = os.path.join(folder, unique_id + ".csv")
        if not os.path.exists(filename):
            logging.warning("%s with ID %s does not exist.", module, unique_id)
            return
        # Read the existing data and update with new values
        data = read_module_csv(module, unique_id)
        data.update(updated_data)
        # Write the updated data back to the file
        with open(filename, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerow(data)
        logging.info("%s with ID %s has been updated.", module, unique_id)
    except Exception as e:
        logging.error("Error updating %s with ID %s: %s", module, unique_id, e)

def delete_module_csv(module, unique_id):
    """
    Deletes the CSV file for the given module and unique ID and removes its ID from the master list.
    """
    try:
        folder = MODULE_FOLDERS.get(module)
        filename = os.path.join(folder, unique_id + ".csv")
        if os.path.exists(filename):
            os.remove(filename)
            logging.info("%s with ID %s has been deleted.", module, unique_id)
        else:
            logging.warning("%s with ID %s does not exist.", module, unique_id)
        
        # Remove the ID from the master file
        id_key = module + "_ID"
        master_file = MASTER_FILES.get(id_key)
        if master_file:
            rows = []
            with open(master_file, mode='r', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["ID"] != unique_id:
                        rows.append(row)
            with open(master_file, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=["ID"])
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        else:
            logging.error("Master file not found for deletion for module: %s", module)
    except Exception as e:
        logging.error("Error deleting %s with ID %s: %s", module, unique_id, e)

# -----------------------------------------
# CRUD Functions for Each Module with error handling
# -----------------------------------------

# ----- USER CRUD -----
def create_user(user_name, user_username, user_phone, user_privlege, user_email):
    try:
        user_id = generate_unique_ID("User_ID")
        if not user_id:
            raise Exception("Failed to generate user ID")
        data = {
            "User_ID": user_id,
            "User_Name": user_name,
            "User_Username": user_username,
            "User_Phone": user_phone,
            # Convert dictionary to JSON string for storage in CSV
            "User_Privlege": json.dumps(user_privlege),
            "User_Email": user_email
        }
        write_module_csv("User", data)
        logging.info("User created with ID: %s", user_id)
        return user_id
    except Exception as e:
        logging.error("Error creating user: %s", e)
        return None

def read_user(user_id):
    data = read_module_csv("User", user_id)
    if data:
        try:
            data["User_Privlege"] = json.loads(data["User_Privlege"])
        except Exception as e:
            logging.error("Error decoding User_Privlege: %s", e)
    return data

def update_user(user_id, updated_data):
    try:
        if "User_Privlege" in updated_data and isinstance(updated_data["User_Privlege"], dict):
            updated_data["User_Privlege"] = json.dumps(updated_data["User_Privlege"])
        update_module_csv("User", user_id, updated_data)
        logging.info("User with ID %s has been updated.", user_id)
    except Exception as e:
        logging.error("Error updating user with ID %s: %s", user_id, e)

def delete_user(user_id):
    delete_module_csv("User", user_id)

# ----- HOUSE CRUD -----
def create_house(house_name, house_address, house_gps, house_owner, house_occupant):
    try:
        house_id = generate_unique_ID("House_ID")
        if not house_id:
            raise Exception("Failed to generate house ID")
        data = {
            "House_ID": house_id,
            "House_Name": house_name,
            "House_Address": house_address,
            "House_GPS": house_gps,
            "House_Owner": json.dumps(house_owner),       # list of owner user IDs
            "House_Occupant": json.dumps(house_occupant)    # list of occupant user IDs
        }
        write_module_csv("House", data)
        logging.info("House created with ID: %s", house_id)
        return house_id
    except Exception as e:
        logging.error("Error creating house: %s", e)
        return None

def read_house(house_id):
    data = read_module_csv("House", house_id)
    if data:
        try:
            data["House_Owner"] = json.loads(data["House_Owner"])
            data["House_Occupant"] = json.loads(data["House_Occupant"])
        except Exception as e:
            logging.error("Error decoding House lists: %s", e)
    return data

def update_house(house_id, updated_data):
    try:
        if "House_Owner" in updated_data and isinstance(updated_data["House_Owner"], list):
            updated_data["House_Owner"] = json.dumps(updated_data["House_Owner"])
        if "House_Occupant" in updated_data and isinstance(updated_data["House_Occupant"], list):
            updated_data["House_Occupant"] = json.dumps(updated_data["House_Occupant"])
        update_module_csv("House", house_id, updated_data)
        logging.info("House with ID %s has been updated.", house_id)
    except Exception as e:
        logging.error("Error updating house with ID %s: %s", house_id, e)

def delete_house(house_id):
    delete_module_csv("House", house_id)

# ----- ROOM CRUD -----
def create_room(room_name, room_floor, room_size, room_house, room_type):
    try:
        room_id = generate_unique_ID("Room_ID")
        if not room_id:
            raise Exception("Failed to generate room ID")
        data = {
            "Room_ID": room_id,
            "Room_Name": room_name,
            "Room_Floor": room_floor,
            "Room_Size": room_size,
            "Room_House": room_house,
            "Room_Type": json.dumps(room_type)  # dictionary stored as JSON
        }
        write_module_csv("Room", data)
        logging.info("Room created with ID: %s", room_id)
        return room_id
    except Exception as e:
        logging.error("Error creating room: %s", e)
        return None

def read_room(room_id):
    data = read_module_csv("Room", room_id)
    if data:
        try:
            data["Room_Type"] = json.loads(data["Room_Type"])
        except Exception as e:
            logging.error("Error decoding Room_Type: %s", e)
    return data

def update_room(room_id, updated_data):
    try:
        if "Room_Type" in updated_data and isinstance(updated_data["Room_Type"], dict):
            updated_data["Room_Type"] = json.dumps(updated_data["Room_Type"])
        update_module_csv("Room", room_id, updated_data)
        logging.info("Room with ID %s has been updated.", room_id)
    except Exception as e:
        logging.error("Error updating room with ID %s: %s", room_id, e)

def delete_room(room_id):
    delete_module_csv("Room", room_id)

# ----- DEVICE CRUD -----
def create_device(device_type, device_name, device_room, device_settings, device_data, device_status):
    try:
        device_id = generate_unique_ID("Device_ID")
        if not device_id:
            raise Exception("Failed to generate device ID")
        data = {
            "Device_ID": device_id,
            "Device_Type": json.dumps(device_type),
            "Device_Name": device_name,
            "Device_Room": device_room,
            "Device_Settings": json.dumps(device_settings),
            "Device_Data": device_data,
            "Device_Status": json.dumps(device_status)
        }
        write_module_csv("Device", data)
        logging.info("Device created with ID: %s", device_id)
        return device_id
    except Exception as e:
        logging.error("Error creating device: %s", e)
        return None

def read_device(device_id):
    data = read_module_csv("Device", device_id)
    if data:
        try:
            data["Device_Type"] = json.loads(data["Device_Type"])
            data["Device_Settings"] = json.loads(data["Device_Settings"])
            data["Device_Status"] = json.loads(data["Device_Status"])
        except Exception as e:
            logging.error("Error decoding device JSON fields: %s", e)
    return data

def update_device(device_id, updated_data):
    try:
        if "Device_Type" in updated_data and isinstance(updated_data["Device_Type"], dict):
            updated_data["Device_Type"] = json.dumps(updated_data["Device_Type"])
        if "Device_Settings" in updated_data and isinstance(updated_data["Device_Settings"], dict):
            updated_data["Device_Settings"] = json.dumps(updated_data["Device_Settings"])
        if "Device_Status" in updated_data and isinstance(updated_data["Device_Status"], dict):
            updated_data["Device_Status"] = json.dumps(updated_data["Device_Status"])
        update_module_csv("Device", device_id, updated_data)
        logging.info("Device with ID %s has been updated.", device_id)
    except Exception as e:
        logging.error("Error updating device with ID %s: %s", device_id, e)

def delete_device(device_id):
    delete_module_csv("Device", device_id)

# -----------------------------------------
# Optional: Example Usage (for manual testing)
# -----------------------------------------
if __name__ == "__main__":
    setup_environment()
    # Example: Uncomment to run a manual test
    # user_id = create_user("Alice", "alice123", "123-456-7890", {"role": "admin"}, "alice@example.com")
    # print("User Data:", read_user(user_id))
