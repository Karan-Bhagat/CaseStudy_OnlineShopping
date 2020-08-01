#Importing SQL
import sqlite3

#Making Connecting
conn = sqlite3.connect('DB1')

#Creating Cursor 
c = conn.cursor()

#Dropping table if already exist in database
table = " DROP TABLE IF EXISTS 'Transaction' "
c.execute(table)

#Creatig Table
c.execute("CREATE TABLE 'Transaction' ( Sequence INTEGER PRIMARY KEY, Transaction_Id VARCHAR(6), Customer_Id VARCHAR(6), Customer_Name VARCHAR(20), Customer_Addr_Id VARCHAR(5), Product_Id VARCHAR(7), Product_Nm VARCHAR(30), ProductPrice VARCHAR(6), ProductQuantity VARCHAR(4), Status VARCHAR(12), Transaction_time_stamp VARCHAR(20), Ordered_Date VARCHAR(11), Shipment_Date VARCHAR(11), Delivered_Date VARCHAR(11), ACTIVE_IND VARCHAR(1))")

#Day 1
#Opening File
file1 = open('Day1.txt')

#Reading File
print('----------------------------------------------------------------------------------------------')
print('Reading File')
print('----------------------------------------------------------------------------------------------')
data1 = file1.read()
print(data1)
print()
print()

#Splitting Rows
print('----------------------------------------------------------------------------------------------')
print('Splitting Rows')
print('----------------------------------------------------------------------------------------------')
data1 = data1.split('\n')
print(data1)
print()
print()

#Removing Blank Row
print('----------------------------------------------------------------------------------------------')
print('Removing Blank Row')
print('----------------------------------------------------------------------------------------------')
data1.remove('')
print(data1)
print()
print()

#Converting Raw Data Into Useable Form of Day 1
print('----------------------------------------------------------------------------------------------')
print('Converting Raw Data Into Useable Form of Day 1')
print('----------------------------------------------------------------------------------------------')
list1 = []
for i in data1:
    dctnry1 = {}
    dctnry1.update({'Transaction_Id' : i[0:6]})
    dctnry1.update({'Customer_Id' : i[6:12]})
    dctnry1.update({'Customer_Name' : i[12:32]})
    dctnry1.update({'Customer_Addr_Id' : i[32:37]})
    dctnry1.update({'Product_Id' : i[37:44]})
    dctnry1.update({'Product_Nm' : i[44:74]})
    dctnry1.update({'ProductPrice' : i[74:80]})
    dctnry1.update({'ProductQuantity' : i[80:84]})
    dctnry1.update({'Status' : i[84:96]})
    dctnry1.update({'Transaction_time_stamp' : i[96:116]})
    dctnry1.update({'Ordered_Date' : i[116:127]})
    dctnry1.update({'Shipment_Date' : i[127:138]})
    dctnry1.update({'Delivered_Date' : i[138:149]})
    list1.append(dctnry1)
print(list1)
print()
print()

#Inserting Values of Day 1 in Table
for dctnry1 in list1:
    dctnry1.update({'ACTIVE_IND' : 'Y'})
    temp_list = []
    for i in dctnry1:
        temp_list.append(dctnry1[i])
    sql = "INSERT INTO 'Transaction' (Transaction_Id, Customer_Id, Customer_Name, Customer_Addr_Id, Product_Id, Product_Nm, ProductPrice, ProductQuantity, Status, Transaction_time_stamp, Ordered_Date, Shipment_Date, Delivered_Date, ACTIVE_IND) VALUES " + str(tuple(temp_list))
    c.execute(sql)
conn.commit()

#Printing Table
print('----------------------------------------------------------------------------------------------')
print("Printing 'Transaction' Table After Day 1")
print('----------------------------------------------------------------------------------------------')
c.execute("SELECT * FROM 'Transaction'")
myresult = c.fetchall()
for x in myresult:
    print(x)
print()
print() 

#Day 2
#Opening File
file2 = open('Day2.txt')

#Reading File
data2 = file2.read()

#Splitting Rows
data2 = data2.split('\n')

#Removing Blank Row
data2.remove('')

#Converting Raw Data Into Useable Form of Day 2
list2 = []
for i in data2:
    dctnry2 = {}
    dctnry2.update({'Transaction_Id' : i[0:6]})
    dctnry2.update({'Customer_Id' : i[6:12]})
    dctnry2.update({'Customer_Name' : i[12:32]})
    dctnry2.update({'Customer_Addr_Id' : i[32:37]})
    dctnry2.update({'Product_Id' : i[37:44]})
    dctnry2.update({'Product_Nm' : i[44:74]})
    dctnry2.update({'ProductPrice' : i[74:80]})
    dctnry2.update({'ProductQuantity' : i[80:84]})
    dctnry2.update({'Status' : i[84:96]})
    dctnry2.update({'Transaction_time_stamp' : i[96:116]})
    dctnry2.update({'Ordered_Date' : i[116:127]})
    dctnry2.update({'Shipment_Date' : i[127:138]})
    dctnry2.update({'Delivered_Date' : i[138:149]})
    list2.append(dctnry2)

#Fetching Data from Table for Main Logic
c.execute("SELECT * FROM 'Transaction'")
myresult = c.fetchall()

#Creating List of Columns names Malually
column_list = ['Sequence' ,'Transaction_Id', 'Customer_Id', 'Customer_Name', 'Customer_Addr_Id', 'Product_Id', 'Product_Nm', 'ProductPrice', 'ProductQuantity', 'Status', 'Transaction_time_stamp', 'Ordered_Date', 'Shipment_Date', 'Delivered_Date', 'ACTIVE_IND']

#Collecting Data in Form of List of Dictionaries
final_data = []
for i in range ( len(myresult)):
    dictnry = {}
    for j in range (len(myresult[i])):
        dictnry.update({column_list[j] : myresult[i][j]})
    final_data.append(dictnry)

#Main Logic for Day 2
for dctnry2 in list2:
    flag = 0
    for j in final_data:
        if j['Transaction_Id'] == dctnry2['Transaction_Id'] and j['Customer_Id'] == dctnry2['Customer_Id'] and j['Product_Id'] == dctnry2['Product_Id']:
            flag = 1
            sql = "UPDATE 'Transaction' SET ACTIVE_IND = 'N' WHERE Transaction_Id = " + str(j['Transaction_Id']) + " and Customer_Id = " + str(j['Customer_Id']) + " and Product_Id = " + str(j['Product_Id'])
            c.execute(sql)
            conn.commit()
            dctnry2.update({'ACTIVE_IND' : 'Y'})
            temp_list = []
            for i in dctnry2:
                temp_list.append(dctnry2[i])
            sql = "INSERT INTO 'Transaction' (Transaction_Id, Customer_Id, Customer_Name, Customer_Addr_Id, Product_Id, Product_Nm, ProductPrice, ProductQuantity, Status, Transaction_time_stamp, Ordered_Date, Shipment_Date, Delivered_Date, ACTIVE_IND) VALUES " + str(tuple(temp_list))
            c.execute(sql)
            break
    if flag == 0:
        dctnry2.update({'ACTIVE_IND' : 'Y'})
        temp_list = []
        for i in dctnry2:
            temp_list.append(dctnry2[i])
        sql = "INSERT INTO 'Transaction' (Transaction_Id, Customer_Id, Customer_Name, Customer_Addr_Id, Product_Id, Product_Nm, ProductPrice, ProductQuantity, Status, Transaction_time_stamp, Ordered_Date, Shipment_Date, Delivered_Date, ACTIVE_IND) VALUES " + str(tuple(temp_list))
        c.execute(sql)
conn.commit()

#Printing Table
print('----------------------------------------------------------------------------------------------')
print("Printing 'Transaction' Table After Day 2")
print('----------------------------------------------------------------------------------------------')
c.execute("SELECT * FROM 'Transaction'")
myresult = c.fetchall()
for x in myresult:
    print(x)
print()
print()

#Day 3
#Opening File
file3 = open('Day3.txt')

#Reading File
data3 = file3.read()

#Splitting Rows
data3 = data3.split('\n')

#Removing Blank Row
data3.remove('')

#Converting Raw Data Into Useable Form of Day 3
list3 = []
for i in data3:
    dctnry3 = {}
    dctnry3.update({'Transaction_Id' : i[0:6]})
    dctnry3.update({'Customer_Id' : i[6:12]})
    dctnry3.update({'Customer_Name' : i[12:32]})
    dctnry3.update({'Customer_Addr_Id' : i[32:37]})
    dctnry3.update({'Product_Id' : i[37:44]})
    dctnry3.update({'Product_Nm' : i[44:74]})
    dctnry3.update({'ProductPrice' : i[74:80]})
    dctnry3.update({'ProductQuantity' : i[80:84]})
    dctnry3.update({'Status' : i[84:96]})
    dctnry3.update({'Transaction_time_stamp' : i[96:116]})
    dctnry3.update({'Ordered_Date' : i[116:127]})
    dctnry3.update({'Shipment_Date' : i[127:138]})
    dctnry3.update({'Delivered_Date' : i[138:149]})
    list3.append(dctnry3)

#Fetching Data from Table for Main Logic
c.execute("SELECT * FROM 'Transaction'")
myresult = c.fetchall()

#Creating List of Columns names Malually
column_list = ['Sequence' ,'Transaction_Id', 'Customer_Id', 'Customer_Name', 'Customer_Addr_Id', 'Product_Id', 'Product_Nm', 'ProductPrice', 'ProductQuantity', 'Status', 'Transaction_time_stamp', 'Ordered_Date', 'Shipment_Date', 'Delivered_Date', 'ACTIVE_IND']

#Collecting Data in Form of List of Dictionaries
final_data = []
for i in range (len(myresult)):
    dictnry = {}
    for j in range (len(myresult[i])):
        dictnry.update({column_list[j] : myresult[i][j]})
    final_data.append(dictnry)

#Main Logic for Day 3
for dctnry3 in list3:
    flag = 0
    for j in final_data:
        if j['Transaction_Id'] == dctnry3['Transaction_Id'] and j['Customer_Id'] == dctnry3['Customer_Id'] and j['Product_Id'] == dctnry3['Product_Id']:
            flag = 1
            sql = "UPDATE 'Transaction' SET ACTIVE_IND = 'N' WHERE Transaction_Id = " + str(j['Transaction_Id']) + " and Customer_Id = " + str(j['Customer_Id']) + " and Product_Id = " + str(j['Product_Id'])
            c.execute(sql)
            conn.commit()
            dctnry3.update({'ACTIVE_IND' : 'Y'})
            temp_list = []
            for i in dctnry3:
                temp_list.append(dctnry3[i])
            sql = "INSERT INTO 'Transaction' (Transaction_Id, Customer_Id, Customer_Name, Customer_Addr_Id, Product_Id, Product_Nm, ProductPrice, ProductQuantity, Status, Transaction_time_stamp, Ordered_Date, Shipment_Date, Delivered_Date, ACTIVE_IND) VALUES " + str(tuple(temp_list))
            c.execute(sql)
            break
    if flag == 0:
        dctnry3.update({'ACTIVE_IND' : 'Y'})
        temp_list = []
        for i in dctnry3:
            temp_list.append(dctnry3[i])
        sql = "INSERT INTO 'Transaction' (Transaction_Id, Customer_Id, Customer_Name, Customer_Addr_Id, Product_Id, Product_Nm, ProductPrice, ProductQuantity, Status, Transaction_time_stamp, Ordered_Date, Shipment_Date, Delivered_Date, ACTIVE_IND) VALUES " + str(tuple(temp_list))
        c.execute(sql)
conn.commit()

#Printing Table
print('----------------------------------------------------------------------------------------------')
print("Printing 'Transaction' Table After Day 3")
print('----------------------------------------------------------------------------------------------')
c.execute("SELECT * FROM 'Transaction'")
myresult = c.fetchall()
for x in myresult:
    print(x)
print()
print()
