import streamlit as st
import pandas as pd
import datetime
import mysql.connector
from mysql.connector import Error
import re

st.set_page_config(layout="wide", page_title="PES Hospital Inventory")

# --- 0. D A T A B A S E   C O N S T A N T S ---
DB_HOST = "localhost"
DB_USER = "root"
DB_NAME = "PES_healthcare"

# --- L O G I N   P A G E ---
def login_page():
    st.title("🔐 Admin Login - PES Hospital Inventory")
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin"

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.logged_in = True
            st.success("Login successful! Redirecting...")
            st.rerun()
        else:
            st.error("Invalid username or password.")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
    st.stop()

# --- 1. D A T A B A S E   C O N N E C T I O N ---
@st.cache_resource(show_spinner=False)
def init_connection(host, user, password, database):
    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        if conn.is_connected():
            return conn
    except Error as e:
        st.error(f"Connection Error: {e}")
        return None

def execute_sql(query, fetch=False):
    conn = st.session_state.get('db_config')
    if conn is None:
        st.error("Database connection not established.")
        return pd.DataFrame() if fetch else "ERROR: Not connected"

    cursor = None
    try:
        if not conn.is_connected():
            conn.reconnect()

        cursor = conn.cursor()

        if query.strip().upper().startswith("SELECT"):
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [i[0] for i in cursor.description]
            return pd.DataFrame(data, columns=columns)

        elif query.strip().upper().startswith("CALL"):
            match = re.match(r"CALL\s+([\w]+)\((.*)\)", query.strip(), re.I)
            if not match:
                raise ValueError(f"Could not parse stored procedure: {query}")
            proc_name, arg_string = match.groups()
            raw_args = [p.strip().strip("'").strip('"') for p in arg_string.split(',')]
            args = []
            for arg in raw_args:
                if arg:
                    try:
                        args.append(int(arg))
                    except ValueError:
                        args.append(arg)
            args_tuple = tuple(args)
            cursor.callproc(proc_name, args_tuple)
            results = []
            for res in cursor.stored_results():
                try:
                    data = res.fetchall()
                    columns = [i[0] for i in res.description]
                    results.append(pd.DataFrame(data, columns=columns))
                except mysql.connector.errors.InterfaceError:
                    pass
            conn.commit()
            return results if results else "SUCCESS: Procedure executed."

        else:
            cursor.execute(query)
            conn.commit()
            return f"SUCCESS: {cursor.rowcount} row(s) affected."

    except Error as e:
        if getattr(e, "sqlstate", None) == '45000':
            return f"TRIGGER ERROR: {e.msg}"
        conn.rollback()
        return f"DATABASE ERROR: {e.msg}"
    finally:
        if cursor:
            cursor.close()

# --- 2. U I   F U N C T I O N S ---

def display_view_data():
    st.subheader("📊 View All Database Tables")
    tables = {
        "Inventory": "SELECT * FROM Inventory",
        "Employee": "SELECT * FROM Employee",
        "Department": "SELECT * FROM Department",
        "Supplier": "SELECT * FROM Supplier",
        "Transaction": "SELECT * FROM Transaction",
        "Inventory Management": "SELECT * FROM Inventory_Management"
    }

    selected_table = st.selectbox("Select a Table:", list(tables.keys()))
    query = tables[selected_table]

    if st.button("🔄 Refresh Table"):
        st.rerun()

    data = execute_sql(query, fetch=True)
    if isinstance(data, pd.DataFrame):
        st.dataframe(data, use_container_width=True)
        st.caption(f"Showing results for {query}")

def display_inventory_management():
    st.subheader("📦 Inventory Stock Operations")

    # --- Add Stock ---
    st.markdown("### ➕ Add Stock")
    with st.form("add_stock", clear_on_submit=True):
        inv_df = execute_sql("SELECT inventory_id, inventory_name FROM Inventory", fetch=True)
        if isinstance(inv_df, pd.DataFrame) and not inv_df.empty:
            inventory_options = inv_df.apply(lambda r: f"{r['inventory_id']} - {r['inventory_name']}", axis=1)
            item = st.selectbox("Select Item", inventory_options)
            qty = st.number_input("Quantity to Add", min_value=1, step=1)
            submitted = st.form_submit_button("Add Stock")
            if submitted:
                inv_id = int(item.split(" - ")[0])
                query = f"CALL Add_Inventory_Stock({inv_id}, {qty})"
                res = execute_sql(query)
                st.success("Stock updated!") if "SUCCESS" in str(res) else st.error(res)
                st.rerun()
        else:
            st.warning("No inventory found.")

    st.divider()

    # --- Dispense Inventory ---
    st.markdown("### ➖ Dispense Inventory")
    with st.form("dispense_form", clear_on_submit=True):
        inv_df = execute_sql("SELECT inventory_id, inventory_name, inv_qty FROM Inventory", fetch=True)
        dept_df = execute_sql("SELECT dept_id, dept_name FROM Department", fetch=True)
        emp_df = execute_sql("SELECT emp_id, emp_name FROM Employee", fetch=True)

        if all(isinstance(df, pd.DataFrame) and not df.empty for df in [inv_df, dept_df, emp_df]):
            inventory_options = inv_df.apply(lambda r: f"{r['inventory_id']} - {r['inventory_name']} (Stock: {r['inv_qty']})", axis=1)
            dept_options = dept_df.apply(lambda r: f"{r['dept_id']} - {r['dept_name']}", axis=1)
            emp_options = emp_df.apply(lambda r: f"{r['emp_id']} - {r['emp_name']}", axis=1)

            inv_sel = st.selectbox("Select Item", inventory_options)
            dept_sel = st.selectbox("Select Department", dept_options)
            emp_sel = st.selectbox("Select Employee", emp_options)
            qty = st.number_input("Quantity to Dispense", min_value=1, step=1)
            date = st.date_input("Dispense Date", datetime.date.today())

            submitted = st.form_submit_button("Record Dispense")
            if submitted:
                inv_id = int(inv_sel.split(" - ")[0])
                dept_id = int(dept_sel.split(" - ")[0])
                emp_id = int(emp_sel.split(" - ")[0])
                q = f"INSERT INTO Inventory_Management (inventory_id, purchase_date, dept_id, emp_id, dept_qty) VALUES ({inv_id}, '{date}', {dept_id}, {emp_id}, {qty})"
                res = execute_sql(q)
                st.success("Dispense recorded!") if "SUCCESS" in str(res) else st.error(res)
                st.rerun()
        else:
            st.warning("Could not load required data.")

def display_reports_and_transactions():
    st.subheader("📈 Transaction Processing and Reporting")

    # --- Process Pending Transactions ---
    st.markdown("### 🔄 Process Pending Transactions")
    with st.form("process_transactions"):
        process_date = st.date_input("Process Date", datetime.date.today())
        submitted = st.form_submit_button("Process")
        if submitted:
            q = f"CALL Process_Pending_Transactions('{process_date}')"
            results = execute_sql(q)
            if isinstance(results, list):
                st.success("Transactions processed and stock updated.")
                if results and isinstance(results[0], pd.DataFrame) and not results[0].empty:
                    for _, row in results[0].iterrows():
                        st.warning(row["Alert"])
            else:
                st.error(results)

    st.divider()

    # --- Inventory Value ---
    st.markdown("### 💰 Calculate Inventory Value")
    inv_df = execute_sql("SELECT inventory_id, inventory_name FROM Inventory", fetch=True)
    if isinstance(inv_df, pd.DataFrame) and not inv_df.empty:
        opt = inv_df.apply(lambda r: f"{r['inventory_id']} - {r['inventory_name']}", axis=1)
        sel = st.selectbox("Select Item", opt)
        if st.button("Calculate Value"):
            inv_id = int(sel.split(" - ")[0])
            res = execute_sql(f"SELECT Calculate_Inventory_Value({inv_id})", fetch=True)

            if isinstance(res, pd.DataFrame) and not res.empty:
                value = res.iloc[0, 0]
                if value is None:
                    st.warning("No value returned (possibly NULL).")
                else:
                    st.metric(label="Inventory Value", value=value)
            else:
                st.error(f"Could not calculate value. Details: {res}")


    st.divider()

    # --- Expiration ---
    st.markdown("### 📅 Days Until Expiration")
    sel2 = st.selectbox("Select Item for Expiration", opt)

    if st.button("Check Expiration"):
        inv_id = int(sel2.split(" - ")[0])
        res = execute_sql(f"SELECT Days_Until_Expiration({inv_id})", fetch=True)

        # --- Fix: Handle string or DataFrame safely ---
        if isinstance(res, str):
            st.error(f"Database Error: {res}")

        elif res is not None and not res.empty:
            days = res.iloc[0, 0]

            if days is None:
                st.info("No expiration date available for this item.")
            elif days < 0:
                st.error(f"Expired {abs(days)} days ago.")
            elif days < 90:
                st.warning(f"Expires in {days} days.")
            else:
                st.success(f"{days} days until expiration.")
        else:
            st.info("No data found for this item.")
    


    st.divider()
    # --- Show Inventory_Management rows that don't yet exist in Transaction (no dropdown) ---
    #st.markdown("### 🧾 Inventory_Management rows missing from Transaction (for manual insert)")

    q_missing = """
        SELECT im.inventory_id, im.purchase_date, im.dept_id, im.emp_id, im.dept_qty,
               inv.inventory_name, d.dept_name, e.emp_name
        FROM inventory_management im
        JOIN inventory inv ON im.inventory_id = inv.inventory_id
        JOIN department d ON im.dept_id = d.dept_id
        JOIN employee e ON im.emp_id = e.emp_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM `transaction` t
            WHERE t.inventory_id = im.inventory_id
              AND t.purchase_date = im.purchase_date
              AND t.dept_id = im.dept_id
              AND t.emp_id = im.emp_id
        );
    """

    _ = execute_sql(q_missing, fetch=True)
   

# --- 🛠️ CRUD PAGE (FIXED) ---
def display_crud_page():
    st.subheader("🛠️ Insert / Update / Delete Data")

    tables = ["Inventory", "Employee", "Department", "Supplier", "Transaction", "Inventory_Management"]
    selected_table = st.selectbox("Select Table", tables)

    action = st.radio("Select Action", ["Insert", "Update", "Delete"])

    df = execute_sql(f"SELECT * FROM {selected_table}", fetch=True)
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.warning("No data available or table not found.")
        return

    # ✅ Always fetch live data
    if st.button("🔄 Refresh Table Data"):
        df = execute_sql(f"SELECT * FROM {selected_table}", fetch=True)
        st.rerun()

    st.dataframe(df, use_container_width=True)

    if action == "Insert":
        st.markdown("### ➕ Insert New Record")

        # ==============================
        # SHOW MISSING INVENTORY ROWS
        # ==============================
        if selected_table.lower() in ["transaction", "transactions"]:
            st.markdown("#### ⚠️ Rows in Inventory Management not yet in Transactions:")
            try:
                inv_df = execute_sql("SELECT * FROM inventory_management", fetch=True)
                trans_df = execute_sql("SELECT * FROM transaction", fetch=True)

                debug_df = execute_sql("SELECT COUNT(*) AS rows_in_transaction FROM transaction", fetch=True)
                st.info(f"DEBUG: {debug_df.iloc[0,0]} rows found in 'transaction' table.")

            

                # ✅ Normalize results into DataFrames
                def to_dataframe(data):
                    if isinstance(data, pd.DataFrame):
                        return data
                    elif isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], dict):
                            return pd.DataFrame(data)
                        elif isinstance(data[0], (list, tuple)):
                            # Convert tuples/lists to DataFrame
                            return pd.DataFrame(data)
                    return pd.DataFrame()  # empty fallback

                inv_df = to_dataframe(inv_df)
                trans_df = to_dataframe(trans_df)

                if inv_df.empty:
                    st.warning("⚠️ No data found in inventory_management.")
                elif trans_df.empty:
                    st.info("ℹ️ Transactions table is empty — all inventory items are missing.")
                    st.dataframe(inv_df)
                else:
                    # Compare only common columns excluding 'amount' and 'status'
                    common_cols = [
                        col for col in inv_df.columns
                        if col in trans_df.columns and col.lower() not in ["amount", "status"]
                    ]

                    if not common_cols:
                        st.warning("⚠️ No common columns found between inventory_management and transactions.")
                    else:
                        missing_rows = inv_df.merge(
                            trans_df[common_cols],
                            on=common_cols,
                            how="left",
                            indicator=True
                        )
                        missing_rows = missing_rows[missing_rows["_merge"] == "left_only"].drop(columns=["_merge"])

                        if not missing_rows.empty:
                            st.dataframe(missing_rows)
                        else:
                            st.info("✅ All inventory items are already in transactions.")

            except Exception as e:
                st.error(f"Error fetching missing rows: {e}")

        # ==============================
        # INSERT FORM
        # ==============================
        with st.form("insert_form"):
            inputs = {}
            for col in df.columns:
                # Skip auto or timestamp columns
                if col.lower() in ["timestamp", "created_at", "updated_at"]:
                    continue
                if col.lower() in ["transaction_id"]:
                    continue

                # Department and Inventory special handling
                if selected_table.lower() == "department":
                    inputs[col] = st.text_input(f"{col}")
                elif selected_table.lower() == "inventory" and col.lower() == "exp_date":
                    inputs[col] = st.text_input(f"{col}", placeholder="Enter NULL for no value")
                else:
                    inputs[col] = st.text_input(f"{col}")

            submitted = st.form_submit_button("Insert")
            if submitted:
                empty_fields = [k for k, v in inputs.items() if v.strip() == ""]
                if empty_fields:
                    st.error(f"Please fill all fields: {', '.join(empty_fields)}")
                else:
                    # ✅ Proceed to insert
                    cols = ", ".join(inputs.keys())
                    
                    def format_sql_value(v):
                        v_stripped = v.strip()
                        if v_stripped.upper() == "NULL" or v_stripped == "":
                            return "NULL"
                        
                        # Try to interpret as number (int or float)
                        try:
                            float(v_stripped)
                            # It's a number, so don't quote it
                            return v_stripped
                        except ValueError:
                            # It's a string (like a date or 'Pending'), so quote it
                            return f"'{v}'"

                    vals = ", ".join([format_sql_value(v) for v in inputs.values()])

                    query = f"INSERT INTO {selected_table} ({cols}) VALUES ({vals})"
                    result = execute_sql(query)
                    if "SUCCESS" in result:
                        st.success("✅ Record inserted successfully!")
                        st.rerun()
                    else:
                        st.error(result)



    elif action == "Update":
        st.markdown("### ✏️ Update Record")
        
        # --- ⬇️ START OF UPDATE FIX ---
        
        key_col = df.columns[0]
        
        # Get list of columns *except* the primary key
        update_cols = [col for col in df.columns if col.lower() != key_col.lower()]
        if not update_cols:
             st.warning(f"No columns available to update for table {selected_table}.")
             return

        record_id = st.number_input(f"Enter {key_col} of record to update", min_value=1)
        col_to_update = st.selectbox("Select Column to Update", update_cols) # <-- Prevents updating PK

        # Use a generic text input, 'NULL' will be handled by our function
        new_val = st.text_input("New Value", placeholder="Type NULL to set null")

        if st.button("Update"):
            # Re-use the same helper function from the Insert block
            def format_sql_value(v):
                v_stripped = v.strip()
                if v_stripped.upper() == "NULL" or v_stripped == "":
                    return "NULL"
                try:
                    float(v_stripped)
                    # It's a number, so don't quote it
                    return v_stripped
                except ValueError:
                    # It's a string, so quote it
                    return f"'{v}'"
            
            formatted_val = format_sql_value(new_val)

            # Use the correctly formatted value in the query
            query = f"UPDATE {selected_table} SET {col_to_update} = {formatted_val} WHERE {key_col} = {record_id}"
            
            # --- ⬆️ END OF UPDATE FIX ---

            result = execute_sql(query)
            if "SUCCESS" in result:
                st.success(result)
                st.rerun()
            else:
                st.error(result)

    elif action == "Delete":
        st.markdown("### 🗑️ Delete Record")

        # Always show which table we're deleting from
        st.info(f"Currently selected table: `{selected_table}`")

        # Ensure we have table data
        if df is None or df.empty:
            st.warning("⚠️ No data found in this table.")
        else:
            # ===============================
            # 🧩 Special Case 1: Inventory Management (Composite Key)
            # ===============================
            if selected_table.strip().lower() == "inventory_management":
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    inv_id = st.number_input("Inventory ID", min_value=1)
                with col2:
                    purchase_date = st.date_input("Purchase Date")
                with col3:
                    dept_id = st.number_input("Department ID", min_value=1)
                with col4:
                    emp_id = st.number_input("Employee ID", min_value=1)

                if st.button("🗑️ Delete Record"):
                    if not (inv_id and purchase_date and dept_id and emp_id):
                        st.warning("⚠️ Please fill all fields before deleting.")
                    else:
                        # Check if record exists before deleting
                        check_query = f"""
                            SELECT 1 FROM inventory_management
                            WHERE inventory_id = {inv_id}
                            AND purchase_date = '{purchase_date}'
                            AND dept_id = {dept_id}
                            AND emp_id = {emp_id};
                        """
                        exists = execute_sql(check_query, fetch=True)

                        if exists is None or isinstance(exists, pd.DataFrame) and exists.empty:
                            st.error("❌ No matching record found.")
                        else:
                            delete_query = f"""
                                DELETE FROM inventory_management
                                WHERE inventory_id = {inv_id}
                                AND purchase_date = '{purchase_date}'
                                AND dept_id = {dept_id}
                                AND emp_id = {emp_id};
                            """
                            result = execute_sql(delete_query)
                            if "SUCCESS" in result:
                                st.success("✅ Record deleted successfully.")
                                st.rerun()
                            else:
                                st.error(result)

            # ===============================
            # E 🧩 Special Case 2: Transaction Table
            # ===============================
            elif selected_table.strip().lower() in ["transaction", "transactions"]:
                key_col = "transaction_id"
                record_id = st.number_input(f"Enter {key_col} to delete", min_value=1)

                if st.button("🗑️ Delete Record"):
                    check_query = f"SELECT 1 FROM transaction WHERE {key_col} = {record_id}"
                    exists = execute_sql(check_query, fetch=True)

                    if exists is None or isinstance(exists, pd.DataFrame) and exists.empty:
                        st.error("❌ No record found with that Transaction ID.")
                    else:
                        delete_query = f"DELETE FROM transaction WHERE {key_col} = {record_id};"
                        result = execute_sql(delete_query)
                        if "SUCCESS" in result:
                            st.success(f"✅ Transaction ID {record_id} deleted successfully.")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to delete record. Error: {result}")

            # ===============================
            # 🧩 Generic Delete for All Other Tables
            # ===============================
            else:
                key_col = df.columns[0]
                record_id = st.number_input(f"Enter {key_col} to delete", min_value=1)
                if st.button("🗑️ Delete Record"):
                    check_query = f"SELECT 1 FROM {selected_table} WHERE {key_col} = {record_id}"
                    exists = execute_sql(check_query, fetch=True)

                    if exists is None or isinstance(exists, pd.DataFrame) and exists.empty:
                        st.error(f"❌ No record found with {key_col}={record_id}.")
                    else:
                        delete_query = f"DELETE FROM {selected_table} WHERE {key_col} = {record_id};"
                        result = execute_sql(delete_query)
                        if "SUCCESS" in result:
                            st.success("✅ Record deleted successfully.")
                            st.rerun()
                        else:
                            st.error(result)




# --- 3. M A I N   A P P ---
st.title("🏥 PES Hospital Inventory Management System")

if 'db_connected' not in st.session_state:
    st.session_state.db_connected = False
if 'db_config' not in st.session_state:
    st.session_state.db_config = None
if 'db_password' not in st.session_state:
    st.session_state.db_password = "varshap1"

connection = init_connection(DB_HOST, DB_USER, st.session_state.db_password, DB_NAME)
if connection:
    st.session_state.db_connected = True
    st.session_state.db_config = connection

    PAGES = {
        "Dashboard / View Data": display_view_data,
        "Inventory Management": display_inventory_management,
        "Transaction & Reporting": display_reports_and_transactions,
        "🛠️ Insert / Update / Delete Data": display_crud_page
    }

    st.sidebar.title("Navigation")
    selection = st.sidebar.radio("Go to:", list(PAGES.keys()))
    page = PAGES[selection]
    page()
else:
    st.error("Connection failed. Enter password below.")
    with st.form("password_form"):
        password = st.text_input("MySQL Root Password", type="password")
        if st.form_submit_button("Connect"):
            temp_conn = init_connection(DB_HOST, DB_USER, password, DB_NAME)
            if temp_conn:
                st.session_state.db_config = temp_conn
                st.session_state.db_password = password
                st.session_state.db_connected = True
                st.rerun()

# --- Styling ---
st.markdown("""
<style>
.stButton>button {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    border-radius: 8px;
    padding: 10px 20px;
}
.stButton>button:hover {
    background-color: #45a049;
}
</style>
""", unsafe_allow_html=True)
