# Hospital Inventory Management System 

A compact, database-driven hospital inventory management system built with **MySQL** and a **Streamlit** admin dashboard.  
This project centralizes tracking of medical supplies, prevents over-dispensing, automates transaction processing, and provides basic reporting and alerts using SQL triggers, procedures, and functions.

---

## Key Features

- Inventory CRUD with quantity and expiry tracking.  
- Departmental dispensing logged with employee accountability.  
- Prevents over-dispensing via a BEFORE INSERT trigger.  
- Automatic stock reduction when transactions are marked COMPLETED.  
- Procedure to process pending transactions and emit low-stock alerts.  
- Functions for computing inventory monetary value and days-until-expiry.  
- Streamlit dashboard for admin workflows: view tables, add stock, dispense, process transactions, compute value.

## Repository Structure

- `ui.py`  
  Streamlit app providing the admin dashboard and forms for all operations.

- `mini_proj_code.sql`  
  SQL script that creates the database schema, sample data, triggers, stored procedures, and functions.

- `README.md`  
  This file.

- `requirements.txt`
  Install using
  ```bash
  pip install -r "requirements.txt"
  
