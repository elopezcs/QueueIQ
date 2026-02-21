# QueueIQ - CareFlow

## Queue Control

## 👥 Author

Mostafa Allahmoradi
Rohit Iyer

## Overview

The QueueControl folder handles the core logic for the QueueIQ project including rush-hour simulations, queue management, live queue data streaming for multiple clinics, and many more features.

## 🎯 How to Run:

1. **Go to QueueControl folder**
    ```bash
    cd QueueControl
    ```

2. **Create a Virtual Environment**
* Windows:
    ```bash
   python -m venv .venv
   ```

* macOS / Linux:
```bash
   python3 -m venv venv
   ```

3. **Activate the Virtual Environment**
* On Windows (Command Prompt):
    ```bash
   .venv\Scripts\Activate
   ```

* On macOS / Linux:
    ```bash
   source venv/bin/activate
   ```

4. **Install Required Dependencies:**

   ```bash
   pip install pandas numpy streamlit
   ```    

5. **Run queue simulation**
    ```bash
    python queue-simulation\backend-queue-simulation.py
    ```
6. **Open a new CLI**

7. **Run live streaming queue dashboard**
    ```bash
    streamlit run queue-simulation\frontend-dashboard.py
    ```