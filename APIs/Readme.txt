# API Overview

## What is an API?

An **API (Application Programming Interface)** is a set of rules and protocols that allow software applications to communicate with each other. APIs define how requests and responses should be formatted, enabling different applications to exchange data and functionality seamlessly.

In the context of this project, the API facilitates the creation, retrieval, updating, and deletion (CRUD) of household objects such as users, houses, rooms, and devices. It provides a structured way for applications to manage and interact with these entities.

---

## How the Program Works

This program provides an API that manages four modules: **Users, Houses, Rooms, and Devices**. Each module follows a **CRUD** (Create, Read, Update, Delete) methodology to store and modify data efficiently.

### 1. **Setup & Environment Initialization**

- The API initializes a `main` directory where data is stored.
- Master CSV files (`User_IDs.csv`, `House_IDs.csv`, `Room_IDs.csv`, `Device_IDs.csv`) maintain unique IDs.
- Separate folders (`Users`, `Houses`, `Rooms`, `Devices`) store CSV records for each module.

### 2. **Generating Unique IDs**

- The function `generate_unique_ID(ID_type)` ensures that each user, house, room, and device receives a **random 9-digit unique ID** that is not already in the master list.

### 3. **CRUD Operations**

Each module has dedicated functions to handle data:

- `create_<module>()`: Generates a new record and saves it as a CSV file.
- `read_<module>()`: Retrieves data from the CSV file.
- `update_<module>()`: Modifies existing records.
- `delete_<module>()`: Removes records and updates master ID lists.

Data is stored in CSV format, ensuring easy readability and compatibility with other applications.

---

## Testing Methodology

The program is tested using **Python's **``** framework** to verify correctness, functionality, and robustness. The `test_api.py` file contains unit tests that:

- Validate ID generation to ensure uniqueness.
- Test each CRUD function by creating, reading, updating, and deleting records.
- Verify data integrity by comparing expected results with actual outcomes.
- Ensure that error handling works properly for invalid inputs.

The tests automatically clean up generated files after execution to maintain a fresh environment for each run.

### **Test Execution**

To run the tests locally, execute:

```sh
python -m unittest discover -v
```

---

## GitHub Actions Workflow

To ensure continuous integration and testing, a **GitHub Actions workflow** is set up in `.github/workflows/python-app.yml`. This workflow automates the testing process whenever code is pushed or a pull request is made.

### **How GitHub Actions Works**

1. **Triggers**: The workflow runs on every `push` or `pull request` to the `main` branch.
2. **Environment Setup**:
   - Checks out the repository.
   - Installs Python and dependencies.
3. **Test Execution**:
   - Changes the working directory to `APIs` where the program files are stored.
   - Runs the `unittest` framework to execute all tests.
4. **Results**:
   - The workflow prints success/failure messages.
   - If a test fails, GitHub Actions marks the workflow as unsuccessful.

### **Running Tests via GitHub Actions**

The workflow is defined in the YAML file:

```yaml
- name: Run Unit Tests
  working-directory: APIs
  run: python -m unittest discover -v
```

This ensures that tests are executed inside the `APIs` folder, preventing import errors.

### **Viewing Results**

- Navigate to the **Actions** tab in your GitHub repository.
- Click on a workflow run to view detailed logs and test outcomes.

---

## Summary

This API provides a structured way to manage household objects using CRUD operations. The system ensures **data integrity, unique identification, and structured storage** through CSV files. Testing is automated via **Python's **``** framework**, and **GitHub Actions** guarantees continuous integration and validation of changes.

By following this workflow, developers can confidently make changes, knowing that the API remains functional and robust.

