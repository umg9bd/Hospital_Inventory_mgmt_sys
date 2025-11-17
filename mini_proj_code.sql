create database if not exists PES_healthcare;
use PES_healthcare;

create table Employee(
emp_id int primary key,
emp_name varchar(100) not null,
emp_contact varchar(20) unique,
emp_address varchar(200));

create table Department(
dept_id int primary key,
dept_name varchar(100) not null,
emp_id int,
constraint FK_Department_Employee foreign key(emp_id)
references EMployee(emp_id)
on update cascade on delete set null);

create table Supplier(
supp_id int primary key,
supp_name varchar(100) not null,
address varchar(255),
supp_contact varchar(20) unique);

create table Inventory(
inventory_id int primary key,
purchase_date date not null,
inventory_name varchar(100) not null,
type varchar(50) not null,
inv_qty int not null check (inv_qty>=0),
exp_date date,
supp_id int,
date_received date,
constraint FK_Inventory_Supplier foreign key(supp_id)
references Supplier(supp_id)
on update cascade on delete set null);

create table Transaction(
transaction_id int primary key,
purchase_date date not null,
inventory_id int,
item_qty int not null check (item_qty>=0),
status varchar(50) not null default 'pending',
amount decimal(10,2) not null,
constraint FK_Transaction_Inventory foreign key(inventory_id)
references Inventory(inventory_id)
on update cascade on delete set null);

create table Inventory_Management(
inventory_id int,
purchase_date date,
dept_id int,
emp_id int,
dept_qty int not null check (dept_qty>=0),
timestamp timestamp default current_timestamp,
constraint PK_Inventory_Management primary key (inventory_id, purchase_date, dept_id, emp_id),
constraint FK_IM_Inventory foreign key(inventory_id)
references Inventory(inventory_id)
on update cascade on delete cascade,
constraint FK_IM_Department foreign key(dept_id)
references Department(dept_id)
on update cascade on delete cascade,
constraint FK_IM_Employee foreign key(emp_id)
references Employee(emp_id)
on update cascade on delete cascade);

INSERT INTO Employee (emp_id, emp_name, emp_contact, emp_address) VALUES
(101, 'Rahul Sharma', '9876543210', '123 Main St'),
(102, 'Priya Singh', '9876543211', '456 Oak Ave'),
(103, 'Siddharth Patel', '9876543212', '789 Pine Ln'),
(104, 'Ananya Gupta', '9876543213', '101 Maple Dr'),
(105, 'Arjun Menon', '9876543214', '202 Birch Rd');

 INSERT INTO Department (dept_id, dept_name, emp_id) VALUES
 (1, 'Cardiology', 101),
 (2, 'Neurology', 102),
 (3, 'Pharmacy', 103),
 (4, 'Radiology', 104),
 (5, 'Laboratory', 105);


INSERT INTO Supplier (supp_id, supp_name, address, supp_contact) VALUES
(201, 'MedTech Supplies', '111 Tech Blvd', '1234567890'),
(202, 'PharmaCorp', '222 Pharma Rd', '1234567891'),
(203, 'Global Instruments', '333 Global St', '1234567892'),
(204, 'Health Goods Inc.', '444 Health Ave', '1234567893'),
(205, 'BioEquip', '555 Bio Way', '1234567894');

INSERT INTO Inventory (inventory_id, purchase_date, inventory_name, type, inv_qty,exp_date, supp_id, date_received) VALUES
(301, '2025-08-15', 'Sterile Gloves', 'Consumable', 500, '2027-12-31', 201, '2025-08-16'),
(302, '2025-09-01', 'Aspirin Tablets', 'Medication', 1000, '2026-06-30',202,'2025-09-02'),
(303, '2025-07-20', 'MRI Machine', 'Equipment', 1, NULL, 203, '2025-07-25'),
(304, '2025-08-25', 'Blood Test Kit', 'Diagnostic', 200, '2026-01-15', 204, '2025-08-26'),
(305, '2025-09-05', 'Surgical Mask', 'Consumable', 1500, '2028-01-31', 201, '2025-09-06');

INSERT INTO Transaction (transaction_id, purchase_date, inventory_id, item_qty, status, amount) VALUES
(401, '2025-08-17', 301, 50, 'COMPLETED', 250.00),
(402, '2025-09-03', 302, 100, 'COMPLETED', 50.00),
(403, '2025-09-04', 305, 200, 'PENDING', 100.00),
(404, '2025-08-27', 304, 20, 'COMPLETED', 40.00),
(405, '2025-09-08', 301, 100, 'PENDING', 500.00);

INSERT INTO Inventory_Management (inventory_id, purchase_date, dept_id, emp_id, dept_qty) VALUES
(301, '2025-08-17', 1, 101, 50),
(302, '2025-09-03', 3, 103, 100),
(305, '2025-09-04', 2, 102, 200),
(304, '2025-08-27', 5, 105, 20),
(301, '2025-09-08', 4, 104, 100);

--trigger to reduce the stock from inventory if the transaction table has the status as completed
DELIMITER //
CREATE TRIGGER stock_reduction
AFTER INSERT ON Transaction
FOR EACH ROW
BEGIN
    IF NEW.status = 'COMPLETED' THEN
        UPDATE Inventory
        SET inv_qty = inv_qty - NEW.item_qty
        WHERE inventory_id = NEW.inventory_id;
    END IF;
END //
DELIMITER ;

--trigger for checking the inventory to prevent over dispense
CREATE TRIGGER check_inventory
BEFORE INSERT ON Inventory_Management
FOR EACH ROW
BEGIN
    DECLARE available_qty INT;
    SELECT inv_qty INTO available_qty
    FROM Inventory
    WHERE inventory_id = NEW.inventory_id;
    IF NEW.dept_qty > available_qty THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Cannot dispense, requested quantity exceeds available inventory stock.';
    END IF;
END //

--trigger to standardize inventory name to uppercase
DELIMITER //
CREATE TRIGGER Standardize_Inventory_Name
BEFORE INSERT ON Inventory
FOR EACH ROW
BEGIN
    SET NEW.inventory_name = TRIM(UPPER(NEW.inventory_name));
END //
DELIMITER ;

--procedure to change transaction to completed from pending and check low stock
DELIMITER //
CREATE PROCEDURE Process_Pending_Transactions(
    IN p_process_date DATE
)
BEGIN
    DECLARE inventory_name_var VARCHAR(100);
    DECLARE current_qty INT;
    DECLARE done INT DEFAULT FALSE;
    DECLARE cur CURSOR FOR 
        SELECT I.inventory_name, I.inv_qty
        FROM Inventory I
        WHERE I.inv_qty < 100;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    UPDATE Transaction
    SET status = 'COMPLETED'
    WHERE status = 'PENDING' AND purchase_date <= p_process_date;
    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO inventory_name_var, current_qty;
        IF done THEN
            LEAVE read_loop;
        END IF;
        SELECT CONCAT(inventory_name_var, ' is LOW STOCK (', current_qty, ' left). Immediate reorder recommended.') AS Alert;
    END LOOP;
    CLOSE cur;
END //
DELIMITER ;

--procedure to add stock to inventory
DELIMITER //
CREATE PROCEDURE Add_Inventory_Stock(
    IN p_inventory_id INT,
    IN p_quantity_added INT
)
BEGIN
    UPDATE Inventory
    SET inv_qty = inv_qty + p_quantity_added
    WHERE inventory_id = p_inventory_id;
END //
DELIMITER ;

--function to calc inventory value
DELIMITER //
CREATE FUNCTION Calculate_Inventory_Value (p_inventory_id INT)
RETURNS VARCHAR(100)
READS SQL DATA
BEGIN
    DECLARE total_value DECIMAL(10, 2);
    DECLARE current_qty INT;
    DECLARE avg_unit_cost DECIMAL(10, 2);
    SELECT inv_qty INTO current_qty
    FROM Inventory
    WHERE inventory_id = p_inventory_id;
    SELECT AVG(T.amount / T.item_qty) INTO avg_unit_cost
    FROM Transaction T
    WHERE T.inventory_id = p_inventory_id
      AND T.status = 'COMPLETED'
      AND T.item_qty > 0;     
    IF avg_unit_cost IS NULL THEN
        RETURN 'Transaction not completed (No cost data available)'; 
    ELSE
        SET total_value = current_qty * avg_unit_cost;
        RETURN CONCAT('Value: ', FORMAT(total_value, 2));
    END IF;
END //
DELIMITER ;

--function to calculate days until expiration
DELIMITER //
CREATE FUNCTION Days_Until_Expiration (p_inventory_id INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE days INT;
    SELECT DATEDIFF(exp_date, CURDATE()) INTO days
    FROM Inventory
    WHERE inventory_id = p_inventory_id;
    RETURN days;
END //
DELIMITER ;

